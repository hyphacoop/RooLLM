import requests

name = 'github_pull_requests_operations'
emoji = '🛠️'
description = (
    "Perform actions on GitHub pull requests (PR) within a repository. "
    "Supported actions: search, create, comment, update, close, reopen, merge, label and assign. "
)

parameters = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "The action to perform on the pull request.",
            "enum": ["search", "create", "comment", "update", "close", "reopen", "merge", "assign", "label"]
        },
        "org": {"type": "string", "default": "hyphacoop"},
        "repo": {"type": "string", "default": "organizing-private"},
        "number": {"type": "integer", "description": "Pull request number (required for some actions)."},
        "title": {"type": "string", "description": "Title for PR creation/update."},
        "body": {"type": "string", "description": "Body content for PR creation, updates, or comments."},
        "assignee": {"type": "string", "description": "GitHub username to assign a PR."}
    },
    "required": ["action"]
}

# **Mapping actions to tool names**
ACTION_TO_TOOL = {
    "create": "create_pull_request",
    "comment": "comment_github_item",
    "assign": "assign_github_item",
    "close": "close_pull_request",
    "reopen": "reopen_pull_request",
    "merge": "merge_pull_request",
    "search": "search_pull_requests",
    "update": "update_pull_request",
    "label": "add_labels_to_github_item"
}

async def tool(roo, arguments, user):
    action = arguments["action"]

    if action not in ACTION_TO_TOOL:
        return f"❌ Unsupported action: {action}"

    tool_name = ACTION_TO_TOOL[action]

    try:
        # Load the tool dynamically if it's not already loaded
        if tool_name not in roo.tools.tools:
            roo.tools.load_tool(tool_name)

        # Call the specific tool
        return await roo.tools.call(roo, tool_name, arguments, user)

    except Exception as e:
        return f"🚨 Error calling {tool_name}: {str(e)}"
