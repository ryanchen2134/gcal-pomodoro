from util import * #local namespace

num_work_sessions = 5   
repetitions = 3
work_time = 25
small_break = 5
large_break = 15
    
def main():
    
    service = get_calendar_service()
    calendar_id = get_pomodoro_calendar_id(service)

    local_tz = ZoneInfo("America/Los_Angeles")  # Adjust this to your timezone
    start_time = datetime.now(local_tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
    total_minutes = (num_work_sessions * (work_time + small_break) + 
                     (num_work_sessions // repetitions) * (large_break - small_break))
    end_time = start_time + timedelta(minutes=total_minutes)

    overlapping_events = check_overlapping_events(service, calendar_id, start_time, end_time)

    if overlapping_events:
        print("There are overlapping events in the specified time range.")
        choice = input("Choose an option:\n1. Replace all overlapping events\n2. Add anyway (will overlap)\n3. Delete projected overlaps and do nothing.\n4. Abort\nYour choice: ")
        
        if choice == '4':
            print("Operation aborted.")
            return
        elif choice == '3' or choice == '1':
            delete_overlapping_events(overlapping_events, service, calendar_id)
            if(choice == '3'):
                return
    

    pomodoro_events = create_pomodoro_events(service, calendar_id, start_time, num_work_sessions, repetitions, work_time, small_break, large_break)

    batch = service.new_batch_http_request(callback=batch_callback)
    for event in pomodoro_events:
        batch.add(service.events().insert(calendarId=calendar_id, body=event))
    execute_with_backoff(batch.execute, True)

    print(f"Successfully added {len(pomodoro_events)} Pomodoro events to your calendar.")




if __name__ == '__main__':
    main()