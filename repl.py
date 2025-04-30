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
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8')

# --- Auth + Config Setup ---

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

# GitHub App/PAT auth
gh_config = {
    "GITHUB_APP_ID": os.getenv("GITHUB_APP_ID"),
    "GITHUB_PRIVATE_KEY": base64.b64decode(os.getenv("GITHUB_PRIVATE_KEY_BASE64", "")).decode("utf-8"),
    "GITHUB_INSTALLATION_ID": os.getenv("GITHUB_INSTALLATION_ID"),
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN")
}

# Get GitHub token and auth info from either GitHub App or PAT
github_token, auth_method, auth_object = prepare_github_token(gh_config)

if github_token:
    logger.info(f"Successfully configured GitHub token using {auth_method} authentication")
    config["gh_token"] = github_token
    # Store the auth object for potential token refresh
    config["gh_auth_object"] = auth_object
    logger.info(f"GitHub token configured with {auth_method} auth")
else:
    logger.warning("⚠️ GitHub token unavailable")

# Load Google credentials
ENCODED_GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
if ENCODED_GOOGLE_CREDENTIALS:
    try:
        DECODED_GOOGLE_CREDENTIALS = json.loads(base64.b64decode(ENCODED_GOOGLE_CREDENTIALS).decode())
        config["google_creds"] = DECODED_GOOGLE_CREDENTIALS
        logger.info("Successfully loaded Google credentials")
    except Exception as e:
        logger.error(f"Error decoding Google credentials: {e}")

# --- LLM & Bridge Setup ---

from llm_client import LLMClient
from roollm import RooLLM
from mcp_config import MCP_CONFIG

async def init_roollm():
    # 1. Init LLM Client
    llm = LLMClient(
        base_url=os.getenv("ROO_LLM_URL", "http://localhost:11434"),
        model=os.getenv("ROO_LLM_MODEL", "hermes3"),
        username=os.getenv("ROO_LLM_AUTH_USERNAME", ""),
        password=os.getenv("ROO_LLM_AUTH_PASSWORD", "")
    )

    # 2. give it mcp config
    config.update(**MCP_CONFIG)

    # 3. Init RooLLM
    roo = RooLLM(inference=llm, config=config)

    # 4. Initialize bridge to load all tools
    await roo.bridge.initialize()

    for t in roo.bridge.tool_registry.all_tools():
        print(f"✅ registered tool: {t.name} ({t.adapter_name})")

    return roo

# Initialize RooLLM
roo = asyncio.run(init_roollm())

# 5. Who's asking
try:
    user = os.getlogin()
except OSError:
    user = getpass.getuser() or "localTester"

# REPL emoji feedback
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


# --- Main REPL Loop ---

async def main():
    await roo.bridge.initialize()

    print("\n🧠 RooLLM Terminal Chat (now with bridge) — Type 'exit' to quit\n")
    print(f"GitHub auth method: {auth_method or 'None'}\n")

    history = []

    while True:
        await refresh_token_if_needed()
        query = input(f"{user} > ")

        if query.lower() in ["exit", "quit"]:
            print(f"Goodbye {user}!")
            break

        response = await roo.chat(user, query, history, react_callback=print_emoji_reaction)

        print(f"Roo> {response['content']}")
        history.append({"role": "user", "content": f"{user}: {query}"})
        history.append(response)

if __name__ == "__main__":
    asyncio.run(main())
