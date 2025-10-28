import requests
import os

name = 'get_pr_diff'
emoji = '🔍'
description = 'Get the diff of a pull request. By default, it will fetch all files. Use the page parameter to fetch a specific page.'

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
        'pull_number': {
            'type': 'integer',
            'description': 'Pull request number.'
        },
        'page': {
            'type': 'integer',
            'description': 'Page number of the results to fetch. If not provided, all pages will be fetched.',
            'default': None
        },
        'per_page': {
            'type': 'integer',
            'description': 'The number of results per page (max 100).',
            'default': 30
        }
    },
    'required': ['pull_number']
}

GITHUB_API_BASE_URL = 'https://api.github.com'

async def tool(roo, arguments, user):
    token = roo.config.get('gh_token') if roo.config else None

    if not token:
        return 'GitHub token is missing.'

    org = arguments.get('org') or os.getenv('DEFAULT_GITHUB_ORG', 'hyphacoop')
    repo = arguments.get('repo') or os.getenv('DEFAULT_GITHUB_REPO', 'organizing-private')
    pull_number = arguments.get('pull_number')
    page = arguments.get('page')
    per_page = arguments.get('per_page', 30)

    if not pull_number:
        return 'Pull request number is required.'

    headers = {'Authorization': f'token {token}'}
    diff_url = f'{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{pull_number}/files'
    
    all_files = []
    if page:
        # Fetch a specific page
        params = {'page': page, 'per_page': per_page}
        try:
            response = requests.get(diff_url, headers=headers, params=params)
            if response.status_code == 200:
                files = response.json()
                if not files:
                    return f'No files found in PR #{pull_number} of \'{org}/{repo}\' for page {page}.'
                all_files.extend(files)
            elif response.status_code == 404:
                return f'❌ PR #{pull_number} not found in \'{org}/{repo}\'.'
            else:
                return f'GitHub API Error: {response.status_code} - {response.text}'
        except Exception as e:
            return f'There was an error while getting the PR diff: {str(e)}'
    else:
        # Fetch all pages
        current_page = 1
        while True:
            params = {'page': current_page, 'per_page': 100}
            try:
                response = requests.get(diff_url, headers=headers, params=params)
                if response.status_code == 200:
                    files = response.json()
                    if not files:
                        break
                    all_files.extend(files)
                    current_page += 1
                elif response.status_code == 404:
                    return f'❌ PR #{pull_number} not found in \'{org}/{repo}\'.'
                else:
                    return f'GitHub API Error: {response.status_code} - {response.text}'
            except Exception as e:
                return f'There was an error while getting the PR diff: {str(e)}'

    if not all_files:
        return f'No files found in PR #{pull_number} of \'{org}/{repo}\'.'

    diff_text = ''
    for file in all_files:
        diff_text += f'File: {file["filename"]}\n'
        diff_text += f'Status: {file["status"]}\n'
        diff_text += f'Additions: {file["additions"]}\n'
        diff_text += f'Deletions: {file["deletions"]}\n'
        diff_text += f'Changes: {file["changes"]}\n'
        if 'patch' in file:
            diff_text += f'Patch:\n{file["patch"]}\n'
        diff_text += '\n'

    return diff_text
