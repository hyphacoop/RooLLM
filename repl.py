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
    "💻": "`github_dispatcher`: Dispatcher for GitHub operations",
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
    "🌐": "`web_search`: Search the internet for current information using Claude with web search",
    "🧠": "`query`: Search Hypha's handbook and public drive documents with RAG via minima MCP",
    "🧭": "`consensus_analyzer`: Analyzes a conversation (list of messages) to identify agreements, disagreements, sentiment, and provide a summary. Conclude with a list of 1-3 suggested next steps.",
    "🔮": "`analyze_meeting_notes`: Analyze Co-Creation Labs meeting notes to gather insights and answer questions"
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

# Load Claude API key
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if CLAUDE_API_KEY:
    config["CLAUDE_API_KEY"] = CLAUDE_API_KEY
    logger.debug("Successfully loaded Claude API key")
else:
    logger.warning("⚠️ Claude API key not found in environment variables")

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
                print(f"{BOLD}{YELLOW}/models{RESET} - List available Ollama models")
                print(f"{BOLD}{YELLOW}/model <model_name>{RESET} - Change the current LLM model")
                print(f"{BOLD}{YELLOW}/current-model{RESET} - Show the current LLM model")
                print(f"{BOLD}{YELLOW}/benchmark [dataset]{RESET} - Run benchmark evaluation")
                print(f"{BOLD}{YELLOW}/analytics [days]{RESET} - Show quality analytics")
                print(f"{BOLD}{YELLOW}/exit{RESET} or {BOLD}{YELLOW}/quit{RESET} - Exit the chat\n")
                continue

            # Handle exit/quit commands
            if query.lower() in ['/exit', '/quit', '/bye']:
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

            # Handle models command
            if query.lower() == '/models':
                await handle_models_command(roo)
                continue

            # Handle model change command
            if query.startswith('/model '):
                new_model = query[7:].strip()
                if new_model:
                    await handle_model_change_command(roo, new_model)
                    continue
                else:
                    print(f"{YELLOW}Please provide a model name after /model{RESET}\n")
                    continue

            # Handle current model command
            if query.lower() == '/current-model':
                await handle_current_model_command(roo)
                continue

            # Handle benchmark commands
            if query.lower().startswith('/benchmark'):
                await handle_benchmark_command(query, roo)
                continue

            # Handle quality analytics command
            if query.lower().startswith('/analytics'):
                await handle_analytics_command(query)
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

async def handle_benchmark_command(query: str, roo_instance):
    """Handle benchmark-related commands."""
    parts = query.split()
    
    if len(parts) == 1:
        # Just '/benchmark' - run default benchmark
        dataset = "all"
    else:
        dataset = parts[1]
    
    print(f"\n{BOLD}{CYAN}🧪 Running Benchmark:{RESET}")
    print(f"{LIME}Dataset: {dataset}{RESET}")
    print(f"{YELLOW}This may take a few minutes...{RESET}\n")
    
    try:
        # Import benchmark runner
        from benchmarks.runners.benchmark_runner import RooLLMBenchmarkRunner
        
        # Create runner
        runner = RooLLMBenchmarkRunner(roo_instance)
        
        # Run benchmark
        results = await runner.run_benchmark(dataset)
        
        if "error" in results:
            print(f"{BOLD}❌ Error: {results['error']}{RESET}\n")
            return
        
        # Display results
        summary = results.get("summary", {})
        print(f"{BOLD}{CYAN}📊 Benchmark Results:{RESET}")
        print(f"{LIME}Total test cases: {summary.get('total_test_cases', 0)}{RESET}")
        print(f"{LIME}Successful evaluations: {summary.get('successful_evaluations', 0)}{RESET}")
        print(f"{LIME}Failed evaluations: {summary.get('failed_evaluations', 0)}{RESET}")
        
        overall_score = summary.get("overall_score", {})
        print(f"{BOLD}{YELLOW}Overall Score: {overall_score.get('mean', 0.0):.2f}{RESET}")
        print(f"{YELLOW}Score Range: {overall_score.get('min', 0.0):.2f} - {overall_score.get('max', 0.0):.2f}{RESET}")
        
        # Show metric breakdown
        metric_stats = summary.get("metric_stats", {})
        if metric_stats:
            print(f"\n{BOLD}{CYAN}Metric Breakdown:{RESET}")
            for metric, stats in metric_stats.items():
                print(f"{LIME}{metric}: {stats.get('mean_score', 0.0):.2f} "
                      f"(success rate: {stats.get('success_rate', 0.0):.1%}){RESET}")
        
        print(f"\n{BOLD}{CYAN}Execution Time: {results.get('execution_time', 0.0):.2f} seconds{RESET}\n")
        
    except ImportError:
        print(f"{BOLD}❌ Error: Benchmarking system not available{RESET}")
        print(f"{YELLOW}Please install deepeval: pip install deepeval{RESET}\n")
    except Exception as e:
        print(f"{BOLD}❌ Error running benchmark: {str(e)}{RESET}\n")
        logger.error(f"Benchmark error: {e}", exc_info=True)

async def handle_analytics_command(query: str):
    """Handle analytics-related commands."""
    parts = query.split()
    
    if len(parts) == 1:
        # Just '/analytics' - show default analytics
        days = 30
    else:
        try:
            days = int(parts[1])
        except ValueError:
            days = 30
    
    print(f"\n{BOLD}{CYAN}📈 Quality Analytics (Last {days} days):{RESET}")
    
    try:
        from stats import get_quality_analytics, get_tool_usage_analytics
        
        # Get quality analytics
        quality_data = get_quality_analytics(days)
        
        if "error" in quality_data:
            print(f"{BOLD}❌ Error: {quality_data['error']}{RESET}\n")
            return
        
        # Display quality analytics
        print(f"{LIME}Total interactions: {quality_data.get('total_interactions', 0)}{RESET}")
        
        manual_feedback = quality_data.get("manual_feedback", {})
        print(f"{LIME}Manual feedback: {manual_feedback.get('positive', 0)}👍 / "
              f"{manual_feedback.get('negative', 0)}👎 ({manual_feedback.get('feedback_rate', 0.0):.1%} response rate){RESET}")
        
        automated_scores = quality_data.get("automated_scores", {})
        if automated_scores.get("count", 0) > 0:
            print(f"{LIME}Automated evaluations: {automated_scores.get('count', 0)}{RESET}")
            print(f"{LIME}Average quality score: {automated_scores.get('average', 0.0):.2f}{RESET}")
            
            # Show distribution
            distribution = automated_scores.get("distribution", {})
            if distribution:
                print(f"{YELLOW}Score distribution:{RESET}")
                for range_key, count in distribution.items():
                    print(f"  {range_key}: {count} responses")
        
        # Get tool usage analytics
        tool_data = get_tool_usage_analytics(days)
        
        if "error" not in tool_data:
            print(f"\n{BOLD}{CYAN}🛠️ Tool Usage Analytics:{RESET}")
            print(f"{LIME}Total tool interactions: {tool_data.get('total_tool_interactions', 0)}{RESET}")
            print(f"{LIME}Unique tools used: {tool_data.get('unique_tools_used', 0)}{RESET}")
            
            # Show top tools
            tool_usage = tool_data.get("tool_usage", {})
            if tool_usage:
                print(f"{YELLOW}Top 5 tools:{RESET}")
                for i, (tool_name, stats) in enumerate(list(tool_usage.items())[:5]):
                    print(f"  {i+1}. {tool_name}: {stats.get('count', 0)} uses "
                          f"({stats.get('usage_percentage', 0.0):.1f}%)")
        
        print()
        
    except ImportError:
        print(f"{BOLD}❌ Error: Analytics not available{RESET}\n")
    except Exception as e:
        print(f"{BOLD}❌ Error getting analytics: {str(e)}{RESET}\n")
        logger.error(f"Analytics error: {e}", exc_info=True)

async def handle_models_command(roo_instance):
    """Handle the /models command to list available Ollama models."""
    print(f"\n{BOLD}{CYAN}🤖 Available Ollama Models:{RESET}")
    
    try:
        # Get the LLM client from RooLLM instance
        llm_client = getattr(roo_instance, "inference", None)
        if llm_client is None:
            print(f"{BOLD}❌ Error: RooLLM is missing an LLM client instance.{RESET}\n")
            return

        base_url = getattr(llm_client, "base_url", None)
        if not base_url:
            print(f"{BOLD}❌ Error: LLM client base URL not configured.{RESET}\n")
            return

        # call the ollama api to get the models
        import aiohttp
        tags_url = f"{base_url.rstrip('/')}/api/tags"

        async with aiohttp.ClientSession(auth=llm_client.auth) as session:
            async with session.get(tags_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m.get("name") if isinstance(m, dict) else m for m in data.get("models", [])]
                    
                    if models:
                        print(f"{LIME}Found {len(models)} model(s):{RESET}")
                        for i, model in enumerate(models, 1):
                            # Highlight current model
                            if model == llm_client.model:
                                print(f"  {BOLD}{YELLOW}{i}. {model} (current){RESET}")
                            else:
                                print(f"  {LIME}{i}. {model}{RESET}")
                    else:
                        print(f"{YELLOW}No models found on the Ollama server.{RESET}")
                else:
                    body = await resp.text()
                    print(f"{BOLD}❌ Error: Failed to fetch models: {resp.status}{RESET}")
                    print(f"{YELLOW}Response: {body}{RESET}")
                    
    except Exception as e:
        print(f"{BOLD}❌ Error listing models: {str(e)}{RESET}")
        logger.error(f"Models command error: {e}", exc_info=True)
    
    print()

async def handle_model_change_command(roo_instance, new_model: str):
    """Handle the /model command to change the current LLM model."""
    print(f"\n{BOLD}{CYAN}🔄 Changing LLM Model:{RESET}")
    
    try:
        # get the LLM client from RooLLM instance
        llm_client = getattr(roo_instance, "inference", None)
        if llm_client is None:
            print(f"{BOLD}❌ Error: RooLLM is missing an LLM client instance.{RESET}\n")
            return

        old_model = llm_client.model
        print(f"{LIME}Current model: {BOLD}{old_model}{RESET}")
        print(f"{LIME}Changing to: {BOLD}{new_model}{RESET}")
        
        # Change the model
        llm_client.model = new_model
        print(f"{BOLD}{YELLOW}✅ Model changed successfully from {old_model} to {new_model}{RESET}")
        
        # Verify the change
        if llm_client.model == new_model:
            print(f"{LIME}Verification: Current model is now {llm_client.model}{RESET}")
        else:
            print(f"{BOLD}⚠️ Warning: Model change may not have taken effect{RESET}")
            
    except Exception as e:
        print(f"{BOLD}❌ Error changing model: {str(e)}{RESET}")
        logger.error(f"Model change error: {e}", exc_info=True)
    
    print()

async def handle_current_model_command(roo_instance):
    """Handle the /current-model command to show the current LLM model."""
    print(f"\n{BOLD}{CYAN}🤖 Current LLM Model:{RESET}")
    
    try:
        # Get the LLM client from RooLLM instance
        llm_client = getattr(roo_instance, "inference", None)
        if llm_client is None:
            print(f"{BOLD}❌ Error: RooLLM is missing an LLM client instance.{RESET}\n")
            return

        current_model = llm_client.model
        base_url = llm_client.base_url
        
        print(f"{LIME}Model: {BOLD}{YELLOW}{current_model}{RESET}")
        print(f"{LIME}Server: {CYAN}{base_url}{RESET}")
        
        # Show if it's a local or remote endpoint
        if "localhost" in base_url or "127.0.0.1" in base_url:
            print(f"{LIME}Type: {CYAN}Local Ollama instance{RESET}")
        else:
            print(f"{LIME}Type: {CYAN}Remote Ollama endpoint{RESET}")
            
    except Exception as e:
        print(f"{BOLD}❌ Error getting current model: {str(e)}{RESET}")
        logger.error(f"Current model command error: {e}", exc_info=True)
    
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print(f"❌ Critical error: {str(e)}")