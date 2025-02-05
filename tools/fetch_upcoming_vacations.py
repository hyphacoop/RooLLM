import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

name = 'fetch_upcoming_vacations'
emoji = '🌴'
description = 'Retrieve upcoming vacations from the company vacation sheet for the next week.'
parameters = {
    'type': 'object',
    'properties': {},
    'required': []
}

def get_google_sheet(sheet_id, tab_name, creds):
    """
    Fetch a Google Sheet by its ID and tab name using provided credentials.
    """
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(tab_name)
    return sheet

def fetch_upcoming_vacations(creds):
    """
    Fetch vacations happening in the upcoming week from the Google Sheet.
    """
    sheet_id = "1QeJNjEn0aHbXahTcojF5YxfpJOwI-cLz0dlS7xPWgS0"
    tab_name = "Vacation"
    sheet = get_google_sheet(sheet_id, tab_name, creds)
    data = sheet.get_all_values()
    
    headers = data[0]
    rows = data[1:]
    vacations = [dict(zip(headers, row)) for row in rows]
    
    today = datetime.date.today()
    one_week_later = today + datetime.timedelta(days=7)
    
    upcoming_vacations = []
    for entry in vacations:
        start_date_str = entry.get('Start of Vacation', '')
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%m/%d/%Y').date()
            if today <= start_date <= one_week_later:
                upcoming_vacations.append(entry)
    
    if not upcoming_vacations:
        return "No vacations in the upcoming week."
    
    vacation_msg = "# 🌴Upcoming Vacations and Out of Office notices😎\n\n"
    for entry in upcoming_vacations:
        start_date = datetime.datetime.strptime(entry['Start of Vacation'], '%m/%d/%Y').date()
        end_date = datetime.datetime.strptime(entry['End of Vacation'], '%m/%d/%Y').date()
        
        date_msg = f"from {start_date.strftime('%A %m/%d/%Y')} to {end_date.strftime('%A %m/%d/%Y')}"
        if start_date == end_date:
            date_msg = f"on {start_date.strftime('%A %m/%d/%Y')}"
            if start_date == today:
                date_msg = "today"
        
        vacation_msg += f"{entry['Employee Name']} is on vacation {date_msg}.\n"
    
    return vacation_msg

async def tool(roo, arguments, user):
    creds_dict = roo.config.get("google_creds")
    if not creds_dict:
        return "Google credentials are missing."
    
    # Convert dictionary to ServiceAccountCredentials object
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)

    vacation_info = fetch_upcoming_vacations(creds)
    return f"Tell {user}, {vacation_info}"
