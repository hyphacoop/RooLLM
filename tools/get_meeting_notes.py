import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

name = "get_meeting_notes"
emoji = "📓"
description = "Retrieve and summarize the latest meeting notes from a specific Google Doc."
parameters = {
    "type": "object",
    "properties": {},
    "required": []
}

# Google Doc ID of the meeting notes document
MEETING_NOTES_DOC_ID = "1CzAluNoyYj9UqofB3LRMNpyt35LFuIVjwYe0P28X9dI"  # This is CoLab's meeting notes document used for testing

def authenticate_google(creds_dict):
    """
    Authenticate and return Google Drive API client using gspread credentials.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents.readonly",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
    
    client = gspread.authorize(creds)
    return creds

def fetch_doc_text(creds, doc_id):
    """
    Fetches the raw text of a Google Doc using the Drive API.
    """
    url = f"https://docs.googleapis.com/v1/documents/{doc_id}?fields=body"
    headers = {"Authorization": f"Bearer {creds.get_access_token().access_token}"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Error fetching document: {response.status_code} {response.text}"

    doc_content = response.json()
    
    # Extract text from Google Doc API response
    text = "\n".join([
        elem["paragraph"]["elements"][0]["textRun"]["content"]
        for elem in doc_content.get("body", {}).get("content", [])
        if "paragraph" in elem and "elements" in elem["paragraph"]
    ])

    print(text)
    
    return text.strip()

async def tool(roo, arguments, user):
    creds_dict = roo.config.get("google_creds")
    if not creds_dict:
        return "Google credentials are missing."
    
    # Authenticate with Google API
    creds = authenticate_google(creds_dict)
    
    # Fetch document text
    meeting_text = fetch_doc_text(creds, MEETING_NOTES_DOC_ID)

    # Simple summary (truncate if too long)
    summary = meeting_text[:500] + "..." if len(meeting_text) > 500 else meeting_text
    
    return f"📜 Latest Meeting Notes:\n\n{summary}"
