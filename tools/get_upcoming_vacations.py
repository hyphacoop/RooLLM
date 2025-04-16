import datetime
import gspread
from google.oauth2 import service_account
import os

name = 'get_upcoming_vacations'
emoji = '🌴'
description = 'Retrieve upcoming vacations from the company vacation sheet for the next week.'
parameters = {
    'type': 'object',
    'properties': {},
    'required': []
}

# Google Sheet configuration
VACATION_SHEET_ID = os.getenv("VACATION_SHEET_ID", "1QeJNjEn0aHbXahTcojF5YxfpJOwI-cLz0dlS7xPWgS0")
VACATION_TAB_NAME = os.getenv("VACATION_TAB_NAME", "Vacation")

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
    sheet = get_google_sheet(VACATION_SHEET_ID, VACATION_TAB_NAME, creds)
    data = sheet.get_all_values()
    
    headers = data[0]
    rows = data[1:]
    vacations = [dict(zip(headers, row)) for row in rows]
    
    # Filter out vacations happening in the next week
    today = datetime.date.today()
    one_week_later = today + datetime.timedelta(days=7)

    upcoming_vacations = []
    for entry in vacations:
        start_date_str = entry['Start of Vacation']
        end_date_str = entry['End of Vacation']
        # Check if the date strings are not empty before converting
        if start_date_str and end_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%m/%d/%Y').date()
            end_date = datetime.datetime.strptime(end_date_str, '%m/%d/%Y').date()
            # Include vacations that are either:
            # 1. Starting in the next week
            # 2. Already in progress
            if (today <= start_date <= one_week_later) or (start_date <= today <= end_date):
                upcoming_vacations.append(entry)
    
    if not upcoming_vacations:
        return "No vacations in the upcoming week."
    
    vacation_msg = "# 🌴 Vacation Status\n\n"
    for entry in upcoming_vacations:
        start_date = datetime.datetime.strptime(entry['Start of Vacation'], '%m/%d/%Y').date()
        end_date = datetime.datetime.strptime(entry['End of Vacation'], '%m/%d/%Y').date()
        
        # Determine the tense based on the dates
        if start_date > today:
            # Future vacation
            date_msg = f"will be away from {start_date.strftime('%A, %B %d')} to {end_date.strftime('%A, %B %d')}"
        elif start_date <= today <= end_date:
            # Current vacation
            date_msg = f"is away until {end_date.strftime('%A, %B %d')}"
        else:
            # Past vacation (shouldn't happen with our filtering, but just in case)
            date_msg = f"was away from {start_date.strftime('%A, %B %d')} to {end_date.strftime('%A, %B %d')}"
        
        vacation_msg += f"• {entry['Employee Name']} {date_msg}\n"
    
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
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

    vacation_info = fetch_upcoming_vacations(creds)
    return f"Tell {user}, {vacation_info}"
