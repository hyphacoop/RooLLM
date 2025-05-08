import os
import sys
import getpass
import asyncio
import json
import base64
import logging
from dotenv import load_dotenv

# Color constants - using softer, more muted colors
LIME = "\033[38;5;108m"      # Softer green
ROO_PURPLE = "\033[38;5;139m"  # Softer purple
PINK = "\033[38;5;175m"      # Softer pink
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[38;5;73m"       # Softer cyan
YELLOW = "\033[38;5;179m"    # Softer yellow

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

# Exit message constant
EXIT_MESSAGE = f"\n{BOLD}{YELLOW}Au revoir!{RESET}"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8', errors='replace')

# --- Auth + Config Setup ---

try:
    from .github_app_auth import GitHubAppAuth, prepare_github_token
except ImportError:
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
    logger.debug(f"Successfully configured GitHub token using {auth_method} authentication")
    config["gh_token"] = github_token
    # Store the auth object for potential token refresh
    config["gh_auth_object"] = auth_object
    logger.debug(f"GitHub token configured with {auth_method} auth")
else:
    logger.warning("⚠️ GitHub token unavailable")

# Load Google credentials
ENCODED_GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
if ENCODED_GOOGLE_CREDENTIALS:
    try:
        DECODED_GOOGLE_CREDENTIALS = json.loads(base64.b64decode(ENCODED_GOOGLE_CREDENTIALS).decode())
        config["google_creds"] = DECODED_GOOGLE_CREDENTIALS
        logger.debug("Successfully loaded Google credentials")
    except Exception as e:
        logger.error(f"Error decoding Google credentials: {e}")

# --- LLM & Bridge Setup ---

try:
    from .llm_client import LLMClient
    from .roollm import RooLLM
    from .mcp_config import MCP_CONFIG
except ImportError:
    from llm_client import LLMClient
    from roollm import RooLLM
    from mcp_config import MCP_CONFIG

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
        logger.info(f"{PINK}{llm.base_url}{RESET}")

        # 2. Update config with MCP configuration
        config.update(**MCP_CONFIG)

        # 3. Init RooLLM
        roo = RooLLM(inference=llm, config=config)

        # 4. Initialize RooLLM and load all tools
        await roo.initialize()

        # Log registered tools
        all_tools = roo.bridge.tool_registry.all_tools()
        logger.info(f"{LIME}{len(all_tools)} Registered tools{RESET}")
        for t in roo.bridge.tool_registry.all_tools():
            logger.debug(f"✅ registered tool: {t.name} ({t.adapter_name})")

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
        print(f"{LIME}└─ {tool_desc}{RESET}")
    else:
        print(f"\n{BOLD}{CYAN}🛠️  Tool Call:{RESET} {emoji}")

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
    global user
    history = []
    
    # Get session username
    try:
        user = getpass.getuser()
    except Exception:
        user = "localTester"
    
    # Handle command line argument if provided
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        try:
            await refresh_token_if_needed()
            response = await roo.chat(user, query, history, react_callback=print_tool_reaction)
            content = response['content'].lstrip('\n')
            print(f"\n{ROO_PURPLE}Roo >{RESET} {content}\n")
        except Exception as e:
            logger.error(f"Error during chat: {e}")
            print(f"❌ Error: {str(e)}")
        return

    # Interactive mode
    print(f"\n{BOLD}{PINK}Welcome to RooLLM Chat!{RESET}")
    print(f"Type {BOLD}'/help'{RESET} to see available commands\n")
    
    while True:
        try:
            print(f"{CYAN}{user} >{RESET} ", end="", flush=True)
            query = input().strip()
            
            if not query:
                continue

            # Handle help command
            if query.lower() == '/help':
                print(f"\n{BOLD}{CYAN}Available Commands:{RESET}")
                print(f"{BOLD}{YELLOW}/username <new_name>{RESET} - Change your username")
                print(f"{BOLD}{YELLOW}/tools{RESET} - List all available tools")
                print(f"{BOLD}{YELLOW}/details :emoji:{RESET} - See tool details")
                print(f"{BOLD}{YELLOW}/exit{RESET} or {BOLD}{YELLOW}/quit{RESET} - Exit the chat\n")
                continue

            # Handle exit/quit commands
            if query.lower() in ['/exit', '/quit']:
                print(EXIT_MESSAGE)
                break

            # Handle username change command
            if query.startswith('/username '):
                new_username = query[10:].strip()
                if new_username:
                    user = new_username
                    print(f"{LIME}Username changed to: {user}{RESET}\n")
                    continue
                else:
                    print(f"{YELLOW}Please provide a username after /username{RESET}\n")
                    continue

            # Handle tools command
            if query.lower() == '/tools':
                print(f"\n{BOLD}{CYAN}Available Tools:{RESET}")
                for emoji, tool_info in emojiToolMap.items():
                    tool_name = tool_info.split(":")[0].strip("`")
                    print(f"{BOLD}{YELLOW}{emoji}\t→ {tool_name}{RESET}")
                print(f"\n{LIME}Use /details :emoji: to see more information about a specific tool{RESET}\n")
                continue

            # Handle details command
            if query.startswith('/details '):
                emoji = query[9:].strip()
                if emoji in emojiToolMap:
                    tool_info = emojiToolMap[emoji]
                    tool_name = tool_info.split(":")[0].strip("`")
                    tool_desc = tool_info.split(":")[1].strip()
                    print(f"\n{BOLD}{CYAN}Tool Details:{RESET}")
                    print(f"{BOLD}{YELLOW}{emoji} {tool_name}{RESET}")
                    print(f"{LIME}└─ {tool_desc}{RESET}\n")
                else:
                    print(f"{YELLOW}Tool with emoji {emoji} not found. Use /tools to see available tools{RESET}\n")
                continue
                
            await refresh_token_if_needed()
            response = await roo.chat(user, query, history, react_callback=print_tool_reaction)
            content = response['content'].lstrip('\n')
            print(f"\n{ROO_PURPLE}Roo >{RESET} {content}\n")
            
        except KeyboardInterrupt:
            print(EXIT_MESSAGE)
            break
        except Exception as e:
            logger.error(f"Error during chat: {e}")
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print(f"❌ Critical error: {str(e)}")