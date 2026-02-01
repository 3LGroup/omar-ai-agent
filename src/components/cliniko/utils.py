from datetime import datetime, timedelta

def subtract_hours_from_time(time_str, hours_to_subtract):
    # Parse the string to a datetime object
    original_time = datetime.fromisoformat(time_str)
    
    # Subtract the specified hours
    new_time = original_time - timedelta(hours=hours_to_subtract)
    
    # Format the new time as UTC
    utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return utc_time_str

def add_hours_to_time(time_str, hours_to_add):
    # Parse the string to a datetime object
    original_time = datetime.fromisoformat(time_str)
    
    # Add the specified hours
    new_time = original_time + timedelta(hours=hours_to_add)
    
    # Format the new time as UTC
    utc_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return utc_time_str