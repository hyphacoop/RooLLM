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

def log_llm_usage(user, emoji=None, tool_used=None, subtool_used=None, response_time=None):
    """Log LLM usage, user, tool calls, and response time."""

    # Semi-anonymized username by hashing
    hashed_username = hashlib.sha256(user.encode()).hexdigest()[:8]  # Use first 8 chars for brevity

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": hashed_username,
        "tool_used": tool_used,  # Main tool name
        "subtool_used": subtool_used,  # Subtool name (if applicable)
        "response_time": response_time  # Log response time in seconds
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
