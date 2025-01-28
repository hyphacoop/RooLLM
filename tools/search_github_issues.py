import requests

name = 'search_github_issues'
emoji = '📂'
description = (
    "Search GitHub issues by organization, repository, and optional filters like label, state, or assignee. "
    "Defaults to searching the 'hyphacoop/organizing-private' repository for open issues. "
    "For example: 'List all open issues' or 'Find issues assigned to @username'."
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'string',
            'description': 'GitHub organization name. Defaults to "hyphacoop".',
            'default': 'hyphacoop'
        },
        'repo': {
            'type': 'string',
            'description': 'Repository name. Defaults to "organizing-private".',
            'default': 'organizing-private'
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
        }
    }
}

GITHUB_API_BASE_URL = "https://api.github.com"
async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None

    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    label = arguments.get("label")  # Optional
    state = arguments.get("state", "open")
    assignee = arguments.get("assignee")  # Optional

    try:
        # Preprocess the assignee to remove '@' if present
        if assignee and assignee.startswith("@"):
            assignee = assignee[1:]

        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues"
        headers = {"Authorization": f"token {token}"}
        params = {"state": state}

        # Add label and assignee only if they're provided
        if label:
            params["labels"] = label
        if assignee:
            params["assignee"] = assignee

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            issues = response.json()
            if not issues:
                filters = []
                if label:
                    filters.append(f"label '{label}'")
                if assignee:
                    filters.append(f"assignee '{assignee}'")
                filters_desc = " and ".join(filters) if filters else "no specific filters"
                return f"No issues found in '{org}/{repo}' with {filters_desc}."

            # Format the output
            issue_list = "\n".join(
                [f"- {issue['title']} ({issue['html_url']})" for issue in issues]
            )
            return f"Found the following issues in '{org}/{repo}':\n{issue_list}"
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while searching issues: {str(e)}"
