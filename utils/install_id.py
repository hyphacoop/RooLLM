#!/usr/bin/env python3
"""
This script helps you get the Installation ID for your GitHub App.
It reads your GitHub App ID and private key from the .env file
and then uses them to authenticate and list all installations.

Usage:
1. Make sure your .env file contains:
   - GITHUB_APP_ID
   - GITHUB_PRIVATE_KEY_BASE64

2. Run this script:
   python get_installation_id.py
"""

import os
import base64
import requests
import jwt
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get GitHub App credentials from .env
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_BASE64 = os.getenv("GITHUB_PRIVATE_KEY_BASE64")

if not GITHUB_APP_ID:
    print("Error: GITHUB_APP_ID not found in .env file")
    exit(1)

if not GITHUB_PRIVATE_KEY_BASE64:
    print("Error: GITHUB_PRIVATE_KEY_BASE64 not found in .env file")
    exit(1)

# Decode the private key
try:
    GITHUB_PRIVATE_KEY = base64.b64decode(GITHUB_PRIVATE_KEY_BASE64).decode('utf-8')
    print("✅ Successfully decoded GitHub private key")
except Exception as e:
    print(f"Error decoding private key: {e}")
    exit(1)

# Generate JWT token
def generate_jwt():
    """Generate a JWT for GitHub App authentication"""
    now = int(time.time())
    payload = {
        'iat': now - 60,  # issued at time (60 seconds ago to allow for clock drift)
        'exp': now + 600,  # expiration time (10 minutes in the future)
        'iss': GITHUB_APP_ID  # issuer (GitHub App ID)
    }
    
    token = jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm='RS256')
    return token

# Get installations
def get_installations():
    """Get all installations for this GitHub App"""
    jwt_token = generate_jwt()
    
    url = "https://api.github.com/app/installations"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GithubAppInstallationFinder"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        exit(1)
    
    return response.json()

# Main
def main():
    print(f"Finding installations for GitHub App ID: {GITHUB_APP_ID}")
    installations = get_installations()
    
    if not installations:
        print("No installations found for this GitHub App.")
        print("You need to install your GitHub App to an organization or user account first.")
        exit(1)
    
    print(f"Found {len(installations)} installation(s):")
    print("\n" + "="*50)
    
    for installation in installations:
        install_id = installation['id']
        account = installation['account']['login']
        account_type = installation['account']['type']
        
        print(f"Installation ID: {install_id}")
        print(f"Account: {account} ({account_type})")
        
        # Show target type (all repos, selected repos)
        target_type = installation.get('repository_selection', 'unknown')
        print(f"Repository Access: {target_type}")
        
        # Get when this was installed and last updated
        created_at = installation.get('created_at', 'unknown')
        updated_at = installation.get('updated_at', 'unknown')
        print(f"Installed: {created_at}")
        print(f"Last updated: {updated_at}")
        
        # Print direct link to configure
        html_url = installation.get('html_url', '')
        if html_url:
            print(f"Configure URL: {html_url}")
            
        print("="*50)
    
    print("\nHow to use:")
    print("1. Add the following to your .env file:")
    print(f"   GITHUB_INSTALLATION_ID=<installation_id>")
    print("2. Make sure you already have the following in your .env file:")
    print("   GITHUB_APP_ID")
    print("   GITHUB_PRIVATE_KEY_BASE64")
    print("   (Optional) GITHUB_TOKEN as fallback")

if __name__ == "__main__":
    main()