import requests

name = 'search_pull_requests'
emoji = '🔍'
description = "Search pull requests with optional filters or retrieve a specific PR by number."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'pr_number': {'type': 'integer', 'description': 'Specific PR number to retrieve.', 'default': None},
        'state': {'type': 'string', 'description': 'State of PRs (open, closed, all).', 'default': 'open', 'enum': ['open', 'closed', 'all']},
        'assignee': {'type': 'string', 'description': 'Filter by assignee.', 'default': None}
    }
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    pr_number = arguments.get("pr_number")  # Optional: Directly search for PR number
    state = arguments.get("state", "open")  # Default to open PRs
    assignee = arguments.get("assignee")  # Optional assignee filter

    headers = {"Authorization": f"token {token}"}

    # If a PR number is provided, fetch that specific PR
    if pr_number:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            pr = response.json()
            return f"🔍 Found PR #{pr_number}: **{pr['title']}**\n{pr['body']}\n[View on GitHub]({pr['html_url']})"
        elif response.status_code == 404:
            return f"⚠️ PR #{pr_number} not found in '{org}/{repo}'."
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    # If no PR number is provided, search PRs with filters
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls"
    params = {"state": state}

    if assignee:
        params["assignee"] = assignee

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        prs = response.json()
        if not prs:
            return f"No pull requests found in '{org}/{repo}' matching the criteria."

        pr_list = "\n".join([f"- {pr['title']} ({pr['html_url']})" for pr in prs])
        return f"🔍 Found the following PRs in '{org}/{repo}':\n{pr_list}"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
