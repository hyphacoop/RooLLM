import requests
import os

name = 'get_pr_diff'
emoji = '🔍'
description = 'Get the diff of a pull request. This tool supports pagination.'

parameters = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'string',
            'description': 'GitHub organization name. Defaults to "hyphacoop".',
            'default': os.getenv('DEFAULT_GITHUB_ORG', 'hyphacoop')
        },
        'repo': {
            'type': 'string',
            'description': 'Repository name. Defaults to "organizing-private".',
            'default': os.getenv('DEFAULT_GITHUB_REPO', 'organizing-private')
        },
        'number': {
            'type': 'integer',
            'description': 'Pull request number.'
        },
        'page': {
            'type': 'integer',
            'description': 'Page number of the results to fetch.',
            'default': 1
        },
        'per_page': {
            'type': 'integer',
            'description': 'The number of results per page (max 100).',
            'default': 30
        }
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = 'https://api.github.com'

async def tool(roo, arguments, user):
    token = roo.config.get('gh_token') if roo.config else None

    if not token:
        return 'GitHub token is missing.'

    org = arguments.get('org') or os.getenv('DEFAULT_GITHUB_ORG', 'hyphacoop')
    repo = arguments.get('repo') or os.getenv('DEFAULT_GITHUB_REPO', 'organizing-private')
    # Accept both 'number' and 'pull_number' for backwards compatibility
    pull_number = arguments.get('number') or arguments.get('pull_number')
    page = arguments.get('page', 1)
    per_page = arguments.get('per_page', 30)

    if not pull_number:
        return 'Pull request number is required.'

    headers = {'Authorization': f'token {token}'}
    diff_url = f'{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{pull_number}/files'
    params = {'page': page, 'per_page': per_page}

    try:
        response = requests.get(diff_url, headers=headers, params=params)

        if response.status_code == 200:
            files = response.json()
            if not files:
                return f'No files found in PR #{pull_number} of \'{org}/{repo}\' for page {page}.'

            diff_text = ''
            for file in files:
                diff_text += f'File: {file["filename"]}\n'
                diff_text += f'Status: {file["status"]}\n'
                diff_text += f'Additions: {file["additions"]}\n'
                diff_text += f'Deletions: {file["deletions"]}\n'
                diff_text += f'Changes: {file["changes"]}\n'
                if 'patch' in file:
                    diff_text += f'Patch:\n{file["patch"]}\n'
                diff_text += '\n'

            return diff_text

        elif response.status_code == 404:
            return f'❌ PR #{pull_number} not found in \'{org}/{repo}\'.'
        else:
            return f'GitHub API Error: {response.status_code} - {response.text}'

    except Exception as e:
        return f'There was an error while getting the PR diff: {str(e)}'
