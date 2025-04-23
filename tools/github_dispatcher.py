name = "github_dispatcher"
description = "Perform GitHub actions like creating, updating, commenting on issues or PRs."
emoji = "💻"

parameters = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "The GitHub action to perform."
        },
        "args": {
            "type": "object",
            "description": "Arguments for the chosen action."
        }
    },
    "required": ["action", "args"]
}

# Map actions to functions, based on the legacy tool modules
ACTION_TO_HANDLER = {
    "add_labels": "tools.github.add_labels_to_github_item.tool",
    "assign": "tools.github.assign_github_item.tool",
    "close_issue": "tools.github.close_github_issue.tool",
    "close_pr": "tools.github.close_pull_request.tool",
    "comment": "tools.github.comment_github_item.tool",
    "create_issue": "tools.github.create_github_issue.tool",
    "create_pr": "tools.github.create_pull_request.tool",
    "merge_pr": "tools.github.merge_pull_request.tool",
    "reopen_issue": "tools.github.reopen_github_issue.tool",
    "reopen_pr": "tools.github.reopen_pull_request.tool",
    "search": "tools.github.search_github_issues.tool",
    "search_issues": "tools.github.search_github_issues.tool",
    "search_prs": "tools.github.search_pull_requests.tool",
    "search_labels": "tools.github.search_repo_labels.tool",
    "update_issue": "tools.github.update_github_issue.tool",
    "update_pr": "tools.github.update_pull_request.tool"
}

async def tool(roo, arguments, user):  
    action = arguments["action"]
    args = arguments

    if action not in ACTION_TO_HANDLER:
        return f"Unsupported GitHub action: {action}"

    module_path, func_name = ACTION_TO_HANDLER[action].rsplit(".", 1)

    try:
        module = __import__(module_path, fromlist=[func_name])
        func = getattr(module, func_name)
        return await func(roo, args, user)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to execute {action}: {type(e).__name__}: {e}"