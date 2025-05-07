import os
import sys
import getpass
import asyncio
import json
import base64
import logging
from dotenv import load_dotenv

LIME = "\033[38;5;118m"
ROO_PURPLE = "\033[38;5;135m"
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"

# Tool emoji mapping
emojiToolMap = {
    "💬": "`comment_github_item`: Add comments to issues or PRs",
    "👤": "`assign_github_item`: Assign users to issues or PRs",
    "🏷️": "`add_labels_to_github_item`: Add labels to issues or PRs",
    "🔖": "`search_repo_labels`: Get available labels in a repository",
    "🔧": "`github_issues_operations`: Dispatcher for issue operations",
    "📝": "`create_github_issue`: Create new issues",
    "🔒": "`close_github_issue`: Close an issue",
    "🔑": "`reopen_github_issue`: Reopen a closed issue",
    "🔍": "`search_github_issues`: Search for issues by status, number, assignee, etc.",
    "📋": "`update_github_issue`: Update issue title/body",
    "🛠️": "`github_pull_requests_operations`: Dispatcher for PR operations",
    "🌿": "`create_pull_request`: Create new PRs",
    "🔐": "`close_pull_request`: Close a PR without merging",
    "🔓": "`reopen_pull_request`: Reopen a closed PR",
    "🔀": "`merge_pull_request`: Merge an open PR",
    "🔎": "`search_pull_requests`: Search for PRs by status, number, assignee, label, etc.",
    "✏️": "`update_pull_request`: Update PR title/body",
    "📖": "`search_handbook`: Search Hypha's handbook",
    "📅": "`get_upcoming_holiday`: Fetch upcoming statutory holidays",
    "🌴": "`get_upcoming_vacations`: Get information about our colleague's upcoming vacations",
    "🗄️": "`get_archive_categories`: List archivable categories with links",
    "🔢": "`calc`: Perform calculations",
    "🧠": "`query`: Search Hypha's handbook and public drive documents with RAG via minima MCP",
    "💻": "`github_dispatcher`: GitHub operations dispatcher"
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8')

# --- Auth + Config Setup ---

from .github_app_auth import GitHubAppAuth, prepare_github_token

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

from .llm_client import LLMClient
from .roollm import RooLLM
from .mcp_config import MCP_CONFIG

async def init_roollm():
    """Initialize the RooLLM instance with LLM client and tools."""
    try:
        # 1. Init LLM Client
        llm = LLMClient(
            base_url=os.getenv("ROO_LLM_URL", "http://localhost:11434"),
            model=os.getenv("ROO_LLM_MODEL", "hermes3"),
            username=os.getenv("ROO_LLM_AUTH_USERNAME", ""),
            password=os.getenv("ROO_LLM_AUTH_PASSWORD", "")
        )

        # 2. Update config with MCP configuration
        config.update(**MCP_CONFIG)

        # 3. Init RooLLM
        roo = RooLLM(inference=llm, config=config)

        # 4. Initialize RooLLM and load all tools
        await roo.initialize()

        # Log registered tools
        logger.info("Registered tools:")
        for t in roo.bridge.tool_registry.all_tools():
            logger.info(f"✅ registered tool: {t.name} ({t.adapter_name})")

        return roo
    except Exception as e:
        logger.error(f"Error initializing RooLLM: {e}", exc_info=True)
        raise

# Initialize RooLLM
try:
    roo = asyncio.run(init_roollm())
except Exception as e:
    logger.error(f"Failed to initialize RooLLM: {e}")
    print(f"❌ Failed to initialize RooLLM: {str(e)}")
    sys.exit(1)

# 5. Who's asking
try:
    user = os.getlogin()
except OSError:
    user = getpass.getuser() or "localTester"

# REPL emoji feedback
async def print_tool_reaction(emoji):
    """Print a styled tool call reaction with emoji and description."""
    if emoji in emojiToolMap:
        tool_info = emojiToolMap[emoji]
        tool_name = tool_info.split(":")[0].strip("`")
        tool_desc = tool_info.split(":")[1].strip()
        print(f"\n{BOLD}{CYAN}🛠️  Tool Call:{RESET}")
        print(f"{BOLD}{YELLOW}{emoji} {tool_name}{RESET}")
        print(f"{LIME}└─ {tool_desc}{RESET}\n")
    else:
        print(f"\n{BOLD}{CYAN}🛠️  Tool Call:{RESET} {emoji}\n")

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
    """Main REPL loop for the RooLLM chat interface."""
    print("\n🧠 RooLLM Terminal Chat — Type 'exit' to quit\n")
    print(f"GitHub auth method: {auth_method or 'None'}\n")

    history = []

    while True:
        try:
            await refresh_token_if_needed()
            query = input(f"{LIME}{user} >{RESET} ")

            if query.lower() in ["exit", "quit"]:
                print(f"Goodbye {user}!")
                break

            response = await roo.chat(user, query, history, react_callback=print_emoji_reaction)

            print(f"{ROO_PURPLE}Roo >{RESET} {response['content']}")
            history.append({"role": "user", "content": f"{user}: {query}"})
            history.append(response)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error during chat: {e}", exc_info=True)
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("{BOLD}{YELLOW}Au revoir{RESET}")
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print(f"❌ Critical error: {str(e)}")