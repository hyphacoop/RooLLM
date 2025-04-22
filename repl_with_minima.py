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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler("roollm_minima.log"),
    ]
)
logger = logging.getLogger(__name__)

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8')

from roollm import (ROLE_USER, make_ollama_inference)
from roollm_with_minima import make_roollm_with_minima
from github_app_auth import prepare_github_token

"""
This script allows local testing of the RooLLMWithMinima class.
You can chat with RooLLM + Minima in a terminal session.

Required environment variables:

    ROO_LLM_AUTH_USERNAME=
    ROO_LLM_AUTH_PASSWORD=
    
    Ask the RooLLM team for the credentials.
    
    - For Minima:
    
        MINIMA_MCP_SERVER_URL=http://localhost:8001
        USE_MINIMA_MCP=true

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

# Check if Minima is enabled
USE_MINIMA = os.getenv("USE_MINIMA_MCP", "false").lower() == "true"
if USE_MINIMA:
    logger.info("Minima integration is enabled")
    MINIMA_SERVER_URL = os.getenv("MINIMA_MCP_SERVER_URL", "http://localhost:8001")
    logger.info(f"Minima server URL: {MINIMA_SERVER_URL}")
else:
    logger.info("Minima integration is disabled")

# Initialize RooLLM with Minima
inference = make_ollama_inference(
    url=os.getenv("ROO_LLM_URL", "https://ai.hypha.coop") + "/api/chat",
    model="hermes3",
    username="hypha",
    password=os.getenv("ROO_LLM_AUTH_PASSWORD", "")
)
roo = make_roollm_with_minima(inference, config=config)

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

# Helper to connect to Minima in the background
async def try_connect_to_minima():
    """Try to connect to Minima but don't block or raise exceptions"""
    try:
        if await roo.connect_to_minima():
            print("✅ Connected to Minima server")
            print(f"🔧 Available Minima tools: {len(roo.minima_tools)}")
            return True
        else:
            print("❌ Could not connect to Minima server")
            print("💡 You can still use RooLLM without Minima")
            print("💡 Type 'connect_minima' at any time to try connecting again")
            return False
    except Exception as e:
        logger.error(f"Error connecting to Minima: {e}")
        print("❌ Error connecting to Minima server")
        print("💡 You can still use RooLLM without Minima")
        print("💡 Type 'connect_minima' at any time to try connecting again")
        return False

# Main REPL loop
async def main():
    print("\nRooLLM with Minima Terminal Chat - Type 'exit' to quit\n")
    print(f"GitHub auth method: {auth_method or 'None'}")
    
    # Try to connect to Minima at startup if enabled
    if USE_MINIMA:
        print("Attempting to connect to Minima server...")
        connected = await try_connect_to_minima()
        if not connected:
            print("You can try connecting again by typing 'connect_minima'")
    
    print("\nReady for chat. Type 'exit' to quit.\n")
    
    history = []
    
    while True:
        # Check if GitHub token needs refresh before each interaction
        await refresh_token_if_needed()
        
        query = input(f"{user} > ")
        
        if query.lower() in ["exit", "quit"]:
            print(f"Goodbye {user}!")
            break
        
        if query.lower() == "minima_status":
            if roo.is_minima_connected():
                print(f"✅ Connected to Minima server")
                print(f"🔧 Available tools: {len(roo.minima_tools)}")
                tool_names = [tool["function"]["name"] for tool in roo.minima_tools]
                print(f"🔧 Tool names: {', '.join(tool_names)}")
            else:
                print("❌ Not connected to Minima server")
                print("💡 Type 'connect_minima' to try connecting")
            continue
        
        if query.lower() == "connect_minima":
            print("Attempting to connect to Minima server...")
            await try_connect_to_minima()
            continue
        
        # Direct query to Minima
        if query.lower().startswith("query "):
            if not roo.is_minima_connected():
                print("❌ Not connected to Minima server")
                print("💡 Type 'connect_minima' to try connecting")
                continue
                
            # Extract query text and run direct Minima query
            query_text = query[6:].strip()  # Remove "query " prefix
            if not query_text:
                print("❓ Please provide search terms after 'query'")
                continue
                
            print(f"🔍 Direct Minima query: \"{query_text}\"")
            result = await roo.minima_adapter.call_tool("query", {"text": query_text})
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
            elif "result" in result:
                # Display the main result
                print(f"\n📚 Results from Minima:\n{result['result']}")
                
                # Show citations more prominently if available
                if "citations" in result:
                    print(f"\n📝 {result['citations']}")
                elif "formatted_sources" in result:
                    print("\n📋 Formatted Sources:")
                    for source in result["formatted_sources"]:
                        print(f"  {source}")
                elif "sources" in result and result["sources"]:
                    print("\n📋 Sources:")
                    for i, source in enumerate(result["sources"]):
                        print(f"- [{i+1}] {source}")
                        
                # Display citation prompt reminder
                if "citation_prompt" in result:
                    print("\n💡 Remember to cite sources when using this information.")
            else:
                print(f"❓ Unexpected result format: {result}")
            continue
            
        # Normal chat flow
        response = await roo.chat(
            user,
            query,
            history,
            react_callback=print_emoji_reaction
        )
        
        # Print the response content
        print(f"Roo> {response['content']}")
        
        history.append({
            'role': ROLE_USER,
            'content': user + ': ' + query
        })
        history.append(response)

if __name__ == "__main__":
    asyncio.run(main()) 