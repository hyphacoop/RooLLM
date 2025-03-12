import os
import sys
import getpass
import asyncio
import json
import base64
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8')

from roollm import (RooLLM, ROLE_USER, make_ollama_inference)
from github_app_auth import GitHubAppAuth, prepare_github_token

"""
This script allows local testing of the RooLLM class with GitHub App authentication.
You can chat with RooLLM in a terminal session.

Required environment variables:

    ROO_LLM_AUTH_USERNAME=
    ROO_LLM_AUTH_PASSWORD=
    
    Ask the RooLLM team for the credentials.
    Github and google credentials are also required.

    - For GitHub App auth: 
    
        GITHUB_APP_ID, GITHUB_INSTALLATION_ID, GITHUB_PRIVATE_KEY_BASE64

    - Fallback: GITHUB_TOKEN (PAT)

    - For Google: GOOGLE_CREDENTIALS (base64 encoded JSON)

Usage:
1. Create an .env file in the project directory with the above variables
2. Run this script to start the REPL
"""

# Load environment variables from .env
load_dotenv()

# Initialize config dictionary
config = {}

# Load GitHub credentials
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", None)
GITHUB_INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID", None)

# Get the base64 encoded private key and decode it
GITHUB_PRIVATE_KEY_BASE64 = os.getenv("GITHUB_PRIVATE_KEY_BASE64", None)
GITHUB_PRIVATE_KEY = None

if GITHUB_PRIVATE_KEY_BASE64:
    try:
        GITHUB_PRIVATE_KEY = base64.b64decode(GITHUB_PRIVATE_KEY_BASE64).decode('utf-8')
        logger.info("Successfully decoded GitHub private key")
    except Exception as e:
        logger.error(f"Error decoding GitHub private key: {e}")

# Prepare GitHub credentials in the format expected by prepare_github_token
gh_config = {
    "GITHUB_APP_ID": GITHUB_APP_ID,
    "GITHUB_PRIVATE_KEY": GITHUB_PRIVATE_KEY,
    "GITHUB_INSTALLATION_ID": GITHUB_INSTALLATION_ID,
    "GITHUB_TOKEN": GITHUB_TOKEN,
}

# Get GitHub token and auth info from either GitHub App or PAT
github_token, auth_method, auth_object = prepare_github_token(gh_config)

if github_token:
    logger.info(f"Successfully configured GitHub token using {auth_method} authentication")
    config["gh_token"] = github_token
    # Store the auth object for potential token refresh
    config["gh_auth_object"] = auth_object
else:
    logger.warning("No GitHub token available")

# Load Google credentials
ENCODED_GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", None)
if ENCODED_GOOGLE_CREDENTIALS:
    try:
        DECODED_GOOGLE_CREDENTIALS = json.loads(base64.b64decode(ENCODED_GOOGLE_CREDENTIALS).decode())
        config["google_creds"] = DECODED_GOOGLE_CREDENTIALS
        logger.info("Successfully loaded Google credentials")
    except Exception as e:
        logger.error(f"Error decoding Google credentials: {e}")

# Initialize RooLLM
inference = make_ollama_inference()
roo = RooLLM(inference, config=config)

# Try to get the current login, otherwise fall back
try:
    user = os.getlogin()
except OSError:
    # Fallback if no controlling terminal (e.g., in Docker or a service)
    user = getpass.getuser() or "localTester"

# Define the callback to print emoji reactions
async def print_emoji_reaction(emoji):
    print(f"> tool call: {emoji}")

# GitHub token refresh helper
async def refresh_token_if_needed():
    """Check if GitHub token needs refresh and update it"""
    if "gh_auth_object" in config:
        auth = config["gh_auth_object"]
        # Get a fresh token (will use cached token if still valid)
        fresh_token = auth.get_token()
        if fresh_token != config.get("gh_token"):
            config["gh_token"] = fresh_token
            logger.info("Refreshed GitHub token")
            # Update RooLLM's config with the new token
            roo.update_config({"gh_token": fresh_token})

# Main REPL loop
async def main():
    print("\nRooLLM Terminal Chat - Type 'exit' to quit\n")
    print(f"GitHub auth method: {auth_method or 'None'}\n")
    
    history = []
    
    while True:
        # Check if GitHub token needs refresh before each interaction
        await refresh_token_if_needed()
        
        query = input(f"{user} > ")
        
        if query.lower() in ["exit", "quit"]:
            print(f"Goodbye {user}!")
            break
            
        response = await roo.chat(
            user,
            query,
            history,
            react_callback=print_emoji_reaction
        )
        
        # Print the response content when working locally
        print(f"Roo> {response['content']}")
        
        history.append({
            'role': ROLE_USER,
            'content': user + ': ' + query
        })
        history.append(response)

if __name__ == "__main__":
    asyncio.run(main())