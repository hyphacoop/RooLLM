import json
import os
from pathlib import Path

def load_tool_constants():
    """Load tool constants from JSON file and return formatted dictionaries for Python and JavaScript."""
    
    # Get the path to the tool_constants.json file
    current_dir = Path(__file__).parent.parent
    constants_file = current_dir / "tool_constants.json"
    
    if not constants_file.exists():
        raise FileNotFoundError(f"Tool constants file not found at {constants_file}")
    
    with open(constants_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    emoji_tool_map = data.get("emojiToolMap", {})
    
    # Format for Python (repl.py style)
    python_format = {}
    for emoji, info in emoji_tool_map.items():
        tool_name = info["tool"]
        description = info["description"]
        python_format[emoji] = f"`{tool_name}`: {description}"
    
    # Format for JavaScript (script.js style)
    js_format = {}
    for emoji, info in emoji_tool_map.items():
        tool_name = info["tool"]
        description = info["description"]
        js_format[emoji] = f"`{tool_name}`:  \n{description}"
    
    return {
        "python_format": python_format,
        "js_format": js_format,
        "raw_data": emoji_tool_map
    }

def get_tool_info(emoji):
    """Get tool information for a specific emoji."""
    constants = load_tool_constants()
    return constants["raw_data"].get(emoji)

def get_all_tools():
    """Get all available tools."""
    constants = load_tool_constants()
    return constants["raw_data"]
