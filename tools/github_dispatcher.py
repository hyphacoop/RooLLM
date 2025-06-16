import logging # Good practice to have a logger
import importlib
import sys # For logging sys.path in case of errors

# It's crucial that the logger for THIS module gets its messages out.
# The name of this logger will be 'hyphadevbot.roollm.tools.github_dispatcher'
# or 'roollm.tools.github_dispatcher' depending on the context.
logger = logging.getLogger(__name__)

# --- Forcefully log __name__ and __package__ at the very start of module execution ---
# These logs will appear when this file is first imported.
logger.debug(f"github_dispatcher: Module loading. __name__ = '{__name__}', __package__ = '{__package__}'")
# --- End initial logging ---

name = "github_dispatcher"
description = "Perform GitHub actions like creating, updating, commenting on issues or PRs. Known actions include search_issues, create_issue, comment, etc."
emoji = "💻"

parameters = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "The GitHub action to perform (e.g., search_issues, create_issue, comment)."
        },
        "org": {
            "type": "string",
            "description": "GitHub organization name (e.g., 'hyphacoop')."
        },
        "repo": {
            "type": "string", 
            "description": "Repository name (e.g., 'matrix-robot', 'organizing-private')."
        },
        "number": {
            "type": "integer",
            "description": "Issue or PR number for actions that operate on specific items."
        },
        "issue_number": {
            "type": "string",
            "description": "Issue number as string (will be converted to integer). Alternative to 'number' parameter."
        },
        "body": {
            "type": "string",
            "description": "Comment text for comment action, or issue/PR body for create/update actions."
        },
        "comment_text": {
            "type": "string", 
            "description": "Comment text (alternative to 'body' parameter for comment action)."
        },
        "text": {
            "type": "string",
            "description": "Text content (alternative to 'body' parameter)."
        },
        "title": {
            "type": "string",
            "description": "Title for create_issue or update_issue actions."
        },
        "assignee": {
            "type": "string",
            "description": "Filter by assignee username for search_issues/list_issues, or assignee for assignment actions."
        },
        "state": {
            "type": "string",
            "description": "Filter by state (e.g., 'open', 'closed') for search_issues/list_issues."
        },
        "query": {
            "type": "string",
            "description": "A specific GitHub search query string for search_issues."
        },
        "labels": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Labels for create_issue or add_labels actions."
        },
        "args": {
            "type": "object",
            "description": "Specific arguments for the chosen action if not covered by top-level params. Arguments in here will be merged with top-level arguments."
        }
    },
    "required": ["action"]
}

# --- Determine BASE_MODULE_PATH ---
base_module_path_source = "Unknown"
if __name__ and '.' in __name__: # Primary strategy: use __name__
    module_path_parts = __name__.split('.')
    # Example: __name__ = 'hyphadevbot.roollm.tools.github_dispatcher'
    # module_path_parts[:-1] = ['hyphadevbot', 'roollm', 'tools']
    # containing_package_path = 'hyphadevbot.roollm.tools'
    containing_package_path = ".".join(module_path_parts[:-1])
    BASE_MODULE_PATH = f"{containing_package_path}.github"
    base_module_path_source = f"derived from __name__ ('{__name__}')"
elif __package__: # Fallback to __package__
    BASE_MODULE_PATH = f"{__package__}.github"
    base_module_path_source = f"derived from __package__ ('{__package__}')"
else:
    # This is the path that led to your ImportError
    logger.error(f"github_dispatcher: CRITICAL - Cannot determine package path for sub-modules. __name__='{__name__}', __package__='{__package__}'.")
    raise ImportError(f"Module '{__name__}' cannot determine its base package path to load sub-modules like '.github.*'. (__package__ was '{__package__}')")

logger.debug(f"github_dispatcher: BASE_MODULE_PATH successfully set to '{BASE_MODULE_PATH}' (source: {base_module_path_source})")

ACTION_TO_HANDLER = {
    "add_labels": f"{BASE_MODULE_PATH}.add_labels_to_github_item.tool",
    "assign": f"{BASE_MODULE_PATH}.assign_github_item.tool",
    "close_issue": f"{BASE_MODULE_PATH}.close_github_issue.tool",
    "close_pr": f"{BASE_MODULE_PATH}.close_pull_request.tool",
    "comment": f"{BASE_MODULE_PATH}.comment_github_item.tool",
    "create_issue": f"{BASE_MODULE_PATH}.create_github_issue.tool",
    "create_pr": f"{BASE_MODULE_PATH}.create_pull_request.tool",
    "list_issues": f"{BASE_MODULE_PATH}.search_github_issues.tool",
    "merge_pr": f"{BASE_MODULE_PATH}.merge_pull_request.tool",
    "reopen_issue": f"{BASE_MODULE_PATH}.reopen_github_issue.tool",
    "reopen_pr": f"{BASE_MODULE_PATH}.reopen_pull_request.tool",
    "search": f"{BASE_MODULE_PATH}.search_github_issues.tool",
    "search_issues": f"{BASE_MODULE_PATH}.search_github_issues.tool",
    "search_labels": f"{BASE_MODULE_PATH}.search_repo_labels.tool",
    "search_prs": f"{BASE_MODULE_PATH}.search_pull_requests.tool",
    "update_issue": f"{BASE_MODULE_PATH}.update_github_issue.tool",
    "update_pr": f"{BASE_MODULE_PATH}.update_pull_request.tool"
}

async def tool(roo_context, arguments, user_identifier=None):  # Renamed for clarity
    action = arguments.get("action")
    
    if not action:
        logger.warning(f"({__name__}) GitHub action not specified in arguments.")
        return "GitHub action not specified."

    if action not in ACTION_TO_HANDLER:
        logger.warning(f"({__name__}) Unsupported GitHub action: '{action}'. Supported: {', '.join(ACTION_TO_HANDLER.keys())}")
        return f"Unsupported GitHub action: {action}. Supported actions are: {', '.join(ACTION_TO_HANDLER.keys())}"

    # Transform arguments based on action type
    transformed_args = transform_arguments(action, arguments)
    
    module_path_str_with_tool_func = ACTION_TO_HANDLER[action]
    module_to_import_path, func_name_in_module = module_path_str_with_tool_func.rsplit('.', 1)

    logger.debug(f"({__name__}) Dispatching action '{action}' to module '{module_to_import_path}' function '{func_name_in_module}' with transformed args: {transformed_args}")

    try:
        module_instance = importlib.import_module(module_to_import_path)
        actual_tool_func = getattr(module_instance, func_name_in_module)
        return await actual_tool_func(roo_context, transformed_args, user_identifier) 
    except ModuleNotFoundError:
        logger.error(f"({__name__}) ModuleNotFoundError while dispatching action '{action}': Could not import '{module_to_import_path}'. Check path and ensure target module exists. sys.path: {sys.path}", exc_info=True)
        return f"Failed to find module for {action}: {module_to_import_path}."
    except AttributeError:
        logger.error(f"({__name__}) AttributeError while dispatching action '{action}': Function '{func_name_in_module}' not found in module '{module_to_import_path}'.", exc_info=True)
        return f"Failed to find function '{func_name_in_module}' in module for {action}: {module_to_import_path}."
    except Exception as e:
        logger.error(f"({__name__}) Exception during execution of dispatched action '{action}' (module: {module_to_import_path}): {e}", exc_info=True)
        return f"Failed to execute {action}: {e}"


def transform_arguments(action, arguments):
    """Transform arguments to match the expected format for each action."""
    # Start with a copy of the original arguments
    transformed = arguments.copy()
    
    # If arguments are nested in 'args', merge them with top-level arguments
    if 'args' in arguments and isinstance(arguments['args'], dict):
        # Top-level arguments take precedence over nested ones
        nested_args = arguments['args'].copy()
        nested_args.update(transformed)
        transformed = nested_args
    
    # Remove the 'action' and 'args' keys as they're not needed by the underlying tools
    transformed.pop('action', None)
    transformed.pop('args', None)
    
    # Action-specific transformations
    if action == "comment":
        # Map various comment parameter names to the expected format
        # comment_github_item expects: org, repo, number (int), body
        
        # Map comment text variations to 'body'
        if 'comment_text' in transformed:
            transformed['body'] = transformed.pop('comment_text')
        elif 'text' in transformed:
            transformed['body'] = transformed.pop('text')
        elif 'comment' in transformed:
            transformed['body'] = transformed.pop('comment')
            
        # Map issue number variations to 'number' and ensure it's an integer
        if 'issue_number' in transformed:
            try:
                transformed['number'] = int(transformed.pop('issue_number'))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert issue_number to integer: {transformed.get('issue_number')}")
        elif 'number' in transformed and isinstance(transformed['number'], str):
            try:
                transformed['number'] = int(transformed['number'])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert number to integer: {transformed.get('number')}")
                
    elif action in ["create_issue", "update_issue"]:
        # These actions expect 'number' as integer if provided
        if 'issue_number' in transformed:
            try:
                transformed['number'] = int(transformed.pop('issue_number'))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert issue_number to integer: {transformed.get('issue_number')}")
        elif 'number' in transformed and isinstance(transformed['number'], str):
            try:
                transformed['number'] = int(transformed['number'])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert number to integer: {transformed.get('number')}")
                
    elif action in ["search_issues", "list_issues"]:
        # These actions might need number conversion too
        if 'issue_number' in transformed:
            try:
                transformed['number'] = int(transformed.pop('issue_number'))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert issue_number to integer: {transformed.get('issue_number')}")
        elif 'number' in transformed and isinstance(transformed['number'], str):
            try:
                transformed['number'] = int(transformed['number'])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert number to integer: {transformed.get('number')}")
    
    logger.debug(f"({__name__}) Argument transformation for action '{action}': {arguments} -> {transformed}")
    return transformed