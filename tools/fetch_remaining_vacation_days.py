import gspread
from google.oauth2 import service_account
import os

name = 'fetch_remaining_vacation_days'
emoji = '🏖️'
description = 'Retrieve the number of remaining vacation days for a specific worker from the vacation sheet.'
parameters = {
    'type': 'object',
    'properties': {
        'employee_name': {
            'type': 'string',
            'description': 'The name of the employee to look up.'
        }
    },
    'required': []
}

# Google Sheet configuration
VACATION_SHEET_ID = os.getenv("VACATION_SHEET_ID", "1QeJNjEn0aHbXahTcojF5YxfpJOwI-cLz0dlS7xPWgS0")
VACATION_TAB_NAME = os.getenv("REMAINING_VACATION_TAB_NAME", "Remaining")

def get_google_sheet(sheet_id, tab_name, creds):
    """
    Fetch a Google Sheet by its ID and tab name using provided credentials.
    """
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(tab_name)
    return sheet

def fetch_remaining_vacation_days(creds, employee_name):
    """
    Fetch remaining vacation days for a specific worker from the Google Sheet.
    """
    sheet = get_google_sheet(VACATION_SHEET_ID, VACATION_TAB_NAME, creds)
    data = sheet.get_all_values()
    
    headers = data[0]
    rows = data[1:]
    vacation_days = [dict(zip(headers, row)) for row in rows]
    
    for entry in vacation_days:
        name = entry.get('Name', '').strip()
        if name.lower() == employee_name.lower():
            days_left = entry.get('Days left', 'N/A')
            return f"{name} has {days_left} vacation days remaining."
    
    return f"No vacation data found for {employee_name}."

# Tool call implementation
async def tool(roo, arguments, user):
    creds_dict = roo.config.get("google_creds")

    if not creds:
        return "Google credentials are missing."
    
    # Convert dictionary to ServiceAccountCredentials object
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    employee_name = arguments.get('employee_name', user)  
    if not employee_name:
        return "Please specify an employee name."
    
    vacation_info = fetch_remaining_vacation_days(creds, employee_name)
    return f"Tell {user}, {vacation_info}"