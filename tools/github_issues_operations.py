import requests

name = 'github_issues_operations'
emoji = '🔧'
description = (
    "Perform actions on GitHub issues within a repository. "
    "Supported actions: search, create, comment, update, close, reopen, label and assign. "
    "For example: 'Assign @username to issue #5 in hyphacoop/organizing-private', "
    "'Comment on issue #7', or 'Search open issues in hyphacoop/hypha.coop'."
)

parameters = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "The action to perform on the issue.",
            "enum": ["search", "create", "comment", "update", "close", "reopen", "assign", "label"]
        },
        "org": {"type": "string", "description": "GitHub organization name.", "default": "hyphacoop"},
        "repo": {"type": "string", "description": "Repository name.", "default": "organizing-private"},
        "issue_number": {"type": "integer", "description": "Issue number (required for some actions)."},
        "title": {"type": "string", "description": "Title for issue creation/update."},
        "body": {"type": "string", "description": "Body content for issue creation, updates, or comments."},
        "assignee": {"type": "string", "description": "GitHub username to assign an issue."},
        "labels": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of labels for issue creation or updates."
        }
    },
    "required": ["action"]
}

# **Mapping actions to tool names**
ACTION_TO_TOOL = {
    "create": "create_github_issue",
    "comment": "comment_github_issue",
    "assign": "assign_github_issue",
    "close": "close_github_issue",
    "reopen": "reopen_github_issue",
    "search": "search_github_issues",
    "update": "update_github_issue",
    "label": "add_labels_to_github_item"
}

async def tool(roo, arguments, user):
    action = arguments["action"]

    # Ensure the requested action is valid
    if action not in ACTION_TO_TOOL:
        return f"❌ Unsupported action: {action}"

    tool_name = ACTION_TO_TOOL[action]

    try:
        # Check if tool is already loaded; if not, load it
        if tool_name not in roo.tools.tools:
            roo.tools.load_tool(tool_name)

        # Call the specific tool using the Tools class
        return await roo.tools.call(roo, tool_name, arguments, user)

    except Exception as e:
        return f"🚨 Error calling {tool_name}: {str(e)}"
