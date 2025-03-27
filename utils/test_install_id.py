#!/usr/bin/env python3
"""
This script tests your GitHub App authentication by:
1. Loading credentials from .env
2. Generating a JWT token
3. Getting an installation token
4. Making a test API call

Usage:
1. Make sure your .env file contains:
   - GITHUB_APP_ID
   - GITHUB_INSTALLATION_ID
   - GITHUB_PRIVATE_KEY_BASE64

2. Run this script:
   python test_github_app_auth.py
"""

import os
import base64
import requests
import jwt
import time
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get GitHub App credentials from .env
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID")
GITHUB_PRIVATE_KEY_BASE64 = os.getenv("GITHUB_PRIVATE_KEY_BASE64")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # PAT fallback

# Validation
missing = []
if not GITHUB_APP_ID:
    missing.append("GITHUB_APP_ID")
if not GITHUB_INSTALLATION_ID:
    missing.append("GITHUB_INSTALLATION_ID")
if not GITHUB_PRIVATE_KEY_BASE64:
    missing.append("GITHUB_PRIVATE_KEY_BASE64")

if missing:
    print(f"Error: Missing required environment variables: {', '.join(missing)}")
    exit(1)

# Decode the private key
try:
    GITHUB_PRIVATE_KEY = base64.b64decode(GITHUB_PRIVATE_KEY_BASE64).decode('utf-8')
    print("✅ Successfully decoded GitHub private key")
except Exception as e:
    print(f"❌ Error decoding private key: {e}")
    exit(1)

# Generate JWT token
def generate_jwt():
    """Generate a JWT for GitHub App authentication"""
    print("Generating JWT token...")
    
    now = int(time.time())
    payload = {
        'iat': now - 60,  # issued at time (60 seconds ago to allow for clock drift)
        'exp': now + 600,  # expiration time (10 minutes in the future)
        'iss': GITHUB_APP_ID  # issuer (GitHub App ID)
    }
    
    try:
        token = jwt.encode(payload, GITHUB_PRIVATE_KEY, algorithm='RS256')
        print("✅ JWT token generated successfully")
        return token
    except Exception as e:
        print(f"❌ Error generating JWT: {e}")
        exit(1)

# Get installation token
def get_installation_token():
    """Get an installation token for the GitHub App"""
    print(f"Getting installation token for installation ID: {GITHUB_INSTALLATION_ID}...")
    
    jwt_token = generate_jwt()
    
    url = f"https://api.github.com/app/installations/{GITHUB_INSTALLATION_ID}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GithubAppAuthTester"
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code != 201:
        print(f"❌ Error getting installation token: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    token = data.get("token")
    expires_at = data.get("expires_at")
    
    if token:
        print(f"✅ Installation token obtained successfully")
        print(f"   Token: {token[:5]}... (expires: {expires_at})")
        return token
    else:
        print("❌ No token in response")
        return None

# Test API call with token
def test_api_call(token):
    """Make a test API call to verify the token works"""
    print("Testing API call with installation token...")
    
    url = "https://api.github.com/installation/repositories"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GithubAppAuthTester"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ API test failed: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    repos = data.get("repositories", [])
    
    print(f"✅ API test successful - Found {len(repos)} accessible repositories")
    
    if repos:
        print("\nAccessible repositories:")
        for repo in repos[:5]:  # Show first 5 repos
            print(f"  - {repo['full_name']}")
        
        if len(repos) > 5:
            print(f"  ... and {len(repos) - 5} more")

# Main
def main():
    print("=== GitHub App Authentication Test ===")
    print(f"App ID: {GITHUB_APP_ID}")
    print(f"Installation ID: {GITHUB_INSTALLATION_ID}")
    print("Private Key: [REDACTED]")
    print("="*36)
    
    # Get installation token
    token = get_installation_token()
    
    if token:
        # Test API call
        test_api_call(token)
        
        print("\n✅ GitHub App authentication is working correctly!")
        print("You can now use it in your application.")
    else:
        print("\n❌ GitHub App authentication failed.")
        
        if GITHUB_TOKEN:
            print("You still have a PAT configured which will be used as fallback.")
        else:
            print("No PAT is configured as fallback.")

if __name__ == "__main__":
    main()