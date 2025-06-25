import requests
import os

name = 'search_github_issues'
emoji = '🔍'
description = (
    "Search GitHub issues by number, organization, repository, and optional filters like label, state, assignee, or text content. "
    "Defaults to searching the 'hyphacoop/organizing-private' repository for open issues. "
    "For example: 'List all open issues', 'Search for issue #42', 'Find issues assigned to @username', or 'Search for issues with title containing Quests'. "
    "To search by title, use query parameter like 'title:Quests' or 'RooLLM Quests in:title'."
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'string',
            'description': 'GitHub organization name. Defaults to "hyphacoop".',
            'default': os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")
        },
        'repo': {
            'type': 'string',
            'description': 'Repository name. Defaults to "organizing-private".',
            'default': os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")
        },
        'number': {
            'type': 'integer',
            'description': 'Issue number to fetch details for. If provided, other filters are ignored.'
        },
        'label': {
            'type': 'string',
            'description': 'Label to filter issues by.'
        },
        'state': {
            'type': 'string',
            'description': 'State of issues (open, closed, all). Defaults to "open".',
            'default': 'open'
        },
        'assignee': {
            'type': 'string',
            'description': 'Assignee to filter by. Use "none" for unassigned issues.',
            'default': None
        },
        'query': {
            'type': 'string',
            'description': 'Text search query to search in issue titles and bodies. Supports GitHub search syntax like "title:Quests" or "Quests in:title".'
        }
    }
}

GITHUB_API_BASE_URL = "https://api.github.com"
async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None

    if not token:
        return "GitHub token is missing."

    org = arguments.get("org") or os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")
    repo = arguments.get("repo") or os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")
    number = arguments.get("number")  # Optional
    label = arguments.get("label")  # Optional
    state = arguments.get("state", "open")
    assignee = arguments.get("assignee")  # Optional
    query = arguments.get("query")  # Optional text search

    headers = {"Authorization": f"token {token}"}

    try:
        if number:
            # Fetch details of a specific issue
            issue_url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}"
            response = requests.get(issue_url, headers=headers)

            if response.status_code == 200:
                issue = response.json()
                assignee_name = issue["assignee"]["login"] if issue.get("assignee") else "Unassigned"
                labels = ", ".join([l["name"] for l in issue.get("labels", [])]) if issue.get("labels") else "No labels"
                issue_state = issue.get("state", "Unknown state")

                return (
                    f"**Issue #{number} - {issue['title']}**\n"
                    f"🔗 {issue['html_url']}\n"
                    f"State: {issue_state}\n"
                    f"Labels: {labels}\n"
                    f"Assignee: {assignee_name}\n\n"
                    f"{issue.get('body', 'No description')}"
                )

            elif response.status_code == 404:
                return f"❌ Issue #{number} not found in '{org}/{repo}'."
            else:
                return f"GitHub API Error: {response.status_code} - {response.text}"

        else:
            # Handle all filters (query, label, assignee, state) together
            # Build search query with repository scope
            search_query = f"repo:{org}/{repo} is:issue"
            
            # Add query filter if specified
            if query:
                search_query += f" {query}"
            
            # Add state filter if specified
            if state and state != "all":
                search_query += f" state:{state}"
            
            # Add label filter if specified
            if label:
                search_query += f" label:\"{label}\""
            
            # Add assignee filter if specified
            if assignee:
                if assignee.lower() == "none":
                    search_query += " no:assignee"
                else:
                    search_query += f" assignee:{assignee.strip('@')}"
            
            search_url = f"{GITHUB_API_BASE_URL}/search/issues"
            params = {"q": search_query, "sort": "updated", "order": "desc"}
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                search_results = response.json()
                issues = search_results.get("items", [])
                
                if not issues:
                    filters = []
                    if query:
                        filters.append(f"query '{query}'")
                    if label:
                        filters.append(f"label '{label}'")
                    if assignee:
                        filters.append(f"assignee '{assignee}'")
                    filters_desc = " and ".join(filters) if filters else "no specific filters"
                    return f"No issues found in '{org}/{repo}' with {filters_desc}."
                
                # Format the output
                issue_list = "\n".join(
                    [f"- {issue['title']} (#{issue['number']}) ({issue['html_url']})" for issue in issues]
                )
                return f"Found {len(issues)} issue(s) in '{org}/{repo}':\n{issue_list}"
            else:
                return f"GitHub Search API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while searching issues: {str(e)}"
