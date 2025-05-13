import os
import json
import hashlib
from datetime import datetime

try:
    from .tools.tool_registry import ToolRegistry
except ImportError:
    from tools.tool_registry import ToolRegistry

# Determine log file path based on environment
SERVER_LOG_PATH = "/home/sysadmin/maubot/llm_usage.json"
LOCAL_LOG_PATH = os.path.expanduser("~/maubot/llm_usage.json")

LLM_LOG_FILE = SERVER_LOG_PATH if os.path.exists(os.path.dirname(SERVER_LOG_PATH)) else LOCAL_LOG_PATH

# Ensure the directory exists
os.makedirs(os.path.dirname(LLM_LOG_FILE), exist_ok=True)

# Instantiate the Tools class
tools_instance = ToolRegistry()

def log_llm_usage(user, request_event_id: str, response_event_id: str, emoji=None, tool_used=None, subtool_used=None, response_time=None):
    """Log LLM usage, user, tool calls, response time, and event IDs for quality assessment."""

    # Semi-anonymized username by hashing
    hashed_username = hashlib.sha256(user.encode()).hexdigest()[:8]  # Use first 8 chars for brevity

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": hashed_username,
        "request_event_id": request_event_id, # ID of the user's message
        "response_event_id": response_event_id, # ID of the bot's message
        "tool_used": tool_used,
        "subtool_used": subtool_used,
        "response_time": response_time,
        "quality_assessment": None  # Placeholder for 👍/👎 feedback
    }

    try:
        # Ensure the log file exists
        if not os.path.exists(LLM_LOG_FILE):
            with open(LLM_LOG_FILE, "w") as f:
                json.dump([], f)

        # Load existing log
        with open(LLM_LOG_FILE, "r") as f:
            logs = json.load(f)

        # Append new entry
        logs.append(entry)

        # Save updated log
        with open(LLM_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)

    except Exception as e:
        print(f"Error writing LLM log: {e}")

def update_llm_log_quality(event_id_of_bot_response: str, quality_assessment: str) -> bool:
    """Update the quality assessment for a given bot's response_event_id in the LLM log."""
    if not os.path.exists(LLM_LOG_FILE):
        print(f"Error: LLM log file not found at {LLM_LOG_FILE}")
        return False

    try:
        with open(LLM_LOG_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: LLM log file {LLM_LOG_FILE} is not valid JSON or is empty.")
                return False
        
        updated = False
        for entry in logs:
            if entry.get("response_event_id") == event_id_of_bot_response: # Match on response_event_id
                entry["quality_assessment"] = quality_assessment
                updated = True
                break
        
        if updated:
            with open(LLM_LOG_FILE, "w") as f:
                json.dump(logs, f, indent=4)
            print(f"Successfully updated quality assessment for response_event_id {event_id_of_bot_response} to {quality_assessment}")
            return True
        else:
            print(f"Warning: response_event_id {event_id_of_bot_response} not found in LLM log for quality update.")
            return False

    except Exception as e:
        print(f"Error updating LLM log quality: {e}")
        return False
