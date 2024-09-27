import os
import json
import time
import webbrowser


from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID_FILE = 'pomodoro_calendar_id.json'

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            try:
                webbrowser.get('firefox %s')
                creds = flow.run_local_server(port=0)
            except webbrowser.Error:
                print("Unable to open Firefox automatically. Please manually visit the authorization URL:")
                creds = flow.run_console()
            
            # Additional check after OAuth flow
            if not creds or not creds.valid:
                raise ValueError("Failed to obtain valid credentials. Please check your authentication process.")
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    # Final check before building the service
    if not creds or not creds.valid:
        raise ValueError("No valid credentials available. Please re-authenticate.")
    
    return build('calendar', 'v3', credentials=creds)

def save_calendar_id(calendar_id):
    with open(CALENDAR_ID_FILE, 'w') as f:
        json.dump({'calendar_id': calendar_id}, f)

def load_calendar_id():
    if os.path.exists(CALENDAR_ID_FILE):
        with open(CALENDAR_ID_FILE, 'r') as f:
            data = json.load(f)
            return data.get('calendar_id')
    return None

def get_pomodoro_calendar_id(service):
    calendar_id = load_calendar_id()
    if calendar_id:
        return calendar_id

    calendar_list = execute_with_backoff(service.calendarList().list)
    
    for calendar in calendar_list.get('items', []):
        if calendar['summary'] == 'Pomodoro':
            save_calendar_id(calendar['id'])
            return calendar['id']
    raise ValueError("Pomodoro calendar not found")



def execute_with_backoff(request, is_batch_request = False, max_retries=5):
    for n in range(max_retries):
        try:
            if(is_batch_request):
                return request()
            return request().execute()
        except HttpError as error:
            if error.resp.status in [403, 500, 503] and n < max_retries - 1:
                delay = 2 ** n
                time.sleep(delay)
            else:
                raise


def check_overlapping_events(service, calendar_id, start_time, end_time):
    # Format the time strings correctly (RFC 3339 format)
    time_min = start_time.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    time_max = end_time.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    try:
        events_result = execute_with_backoff(
            lambda: service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
        )
        events = events_result.get('items', [])
        return events
    except Exception as e:
        print(f"Error in check_overlapping_events: {e}")
        print(f"Calendar ID: {calendar_id}")
        print(f"Time Min: {time_min}")
        print(f"Time Max: {time_max}")
        raise

def delete_overlapping_events(overlapping_events, service, calendar_id):
    batch = service.new_batch_http_request(callback=batch_callback)
    for event in overlapping_events:
        batch.add(service.events().delete(calendarId=calendar_id, eventId=event['id']))
    execute_with_backoff(batch.execute, True)
        
def create_pomodoro_events(service, calendar_id, start_time, num_work_sessions, repetitions, work_time, small_break, large_break):
    events = []
    current_time = start_time

    for i in range(num_work_sessions):
        work_end = current_time + timedelta(minutes=work_time)
        events.append({
            'summary': 'Pomodoro Work Session',
            'start': {'dateTime': current_time.isoformat(), 'timeZone': 'America/Los_Angeles'},
            'end': {'dateTime': work_end.isoformat(), 'timeZone': 'America/Los_Angeles'},
            'colorId': '11'  # Red color for work sessions
        })
        current_time = work_end

        if i < num_work_sessions - 1:
            if (i + 1) % repetitions == 0:
                break_time = large_break
                break_summary = 'Pomodoro Large Break'
            else:
                break_time = small_break
                break_summary = 'Pomodoro Small Break'
            
            break_end = current_time + timedelta(minutes=break_time)
            events.append({
                'summary': break_summary,
                'start': {'dateTime': current_time.isoformat(), 'timeZone': 'America/Los_Angeles'},
                'end': {'dateTime': break_end.isoformat(), 'timeZone': 'America/Los_Angeles'},
                'colorId': '2'  # Green color for breaks
            })
            current_time = break_end

    return events

def batch_callback(request_id, response, exception):
    if exception is not None:
        print(f"Error on request {request_id}: {exception}")
    else:
        print(f"Request {request_id} was successful.")
