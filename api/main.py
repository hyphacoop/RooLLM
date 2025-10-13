import os
import json
import base64
import logging
import asyncio
import sys
import socket
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Port configuration
PORT = int(os.getenv("PORT", "8081"))

# Add parent directory to path to import roollm
sys.path.append(str(Path(__file__).parent.parent))

# Import roollm and related modules
from roollm import RooLLM
from llm_client import LLMClient
from mcp_config import MCP_CONFIG
from github_app_auth import prepare_github_token
from utils.google_credentials import load_all_google_credentials

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# GitHub Setup
gh_config = {
    "GITHUB_APP_ID": os.getenv("GITHUB_APP_ID"),
    "GITHUB_PRIVATE_KEY": base64.b64decode(os.getenv("GITHUB_PRIVATE_KEY_BASE64", "")).decode('utf-8') if os.getenv("GITHUB_PRIVATE_KEY_BASE64") else None,
    "GITHUB_INSTALLATION_ID": os.getenv("GITHUB_INSTALLATION_ID"),
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
}

github_token, auth_method, auth_object = prepare_github_token(gh_config)

# Claude Setup
claude_api_key = os.getenv("CLAUDE_API_KEY")

# Initialize config dictionary
config = {
    "gh_token": github_token,
    "gh_auth_object": auth_object,
    "CLAUDE_API_KEY": claude_api_key
}

# Load all Google credentials using utility function
config.update(load_all_google_credentials())

# Update config with MCP settings
config.update(**MCP_CONFIG)

# Initialize LLM Client
llm = LLMClient(
    base_url=os.getenv("ROO_LLM_URL", "http://localhost:11434"),
    model=os.getenv("ROO_LLM_MODEL", "hermes3"),
    username=os.getenv("ROO_LLM_AUTH_USERNAME", ""),
    password=os.getenv("ROO_LLM_AUTH_PASSWORD", "")
)

# Initialize RooLLM with bridge
roo = RooLLM(inference=llm, config=config)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the bridge when the app starts and clean up when it shuts down"""
    try:
        # Initialize RooLLM which will initialize the bridge
        await roo.initialize()
        logger.debug("RooLLM and Bridge initialized successfully")
        
        # Log registered tools for debugging
        tools = roo.bridge.tool_registry.all_tools()
        logger.debug(f"Successfully loaded {len(tools)} tools:")
        for tool in tools:
            logger.debug(f"✅ registered tool: {tool.name} ({tool.adapter_name})")
    except Exception as e:
        logger.error(f"Failed to initialize RooLLM: {e}", exc_info=True)
        raise
    yield
    # Cleanup code here if needed
    logger.debug("FastAPI Lifespan: Shutdown event")
    try:
        logger.debug("Attempting to call RooLLM cleanup method...")
        await roo.cleanup()
        logger.debug("RooLLM cleanup method called successfully.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)

# App & State
app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

user = os.getenv("ROO_LLM_AUTH_USERNAME", "frontendUser")
histories = {}  # store per-session history
sessions = {}  # store session metadata

def generate_session_title(history):
    """
    Generate an initial prompt for a session based on its history.
    Uses the first user message as the initial prompt, or a default if no messages exist.
    """
    if not history:
        return "New Session"
    
    # Find the first user message
    for message in history:
        if message.get('role') == "user":
            # Take first 50 characters of the message as initial prompt
            initial_prompt = message.get('content', '')[:50]
            if len(initial_prompt) == 50:
                initial_prompt += "..."
            return initial_prompt
    
    return "New Session"

# Schema
class ChatRequest(BaseModel):
    message: str
    session_id: str  # allows tracking sessions from frontend

class MinimaQueryRequest(BaseModel):
    query: str
    session_id: str

@app.post("/chat")
async def chat(request: ChatRequest):
    # Create session metadata if it doesn't exist
    if request.session_id not in sessions:
        sessions[request.session_id] = {
            "id": request.session_id,
            "created_at": time.time() * 1000,  # current time in milliseconds
            "initial_prompt": "New Session",  # Initial prompt
        }

    await refresh_token_if_needed()
    history = histories.get(request.session_id, [])

    async def event_stream():
        queue = asyncio.Queue()

        async def safe_react_callback(emoji):
            logger.info(f"tool call: {emoji}")
            await queue.put({"type": "emoji", "emoji": emoji})

        async def runner():
            # Format the message with username prefix
            user_message = f"{request.message}"
            
            response = await roo.chat(
                user,
                request.message,
                history,
                react_callback=safe_react_callback
            )

            # Add to history with proper format
            history.append({"role": "user", "content": user_message})
            history.append(response)  # response already has the correct format
            histories[request.session_id] = history

            # Update initial prompt if this is the first message
            if len(history) == 2:  # Just added first user and assistant messages
                sessions[request.session_id]["initial_prompt"] = generate_session_title(history)
            
            # Send the response immediately
            await queue.put({"type": "reply", "content": response["content"]})
            await queue.put(None)  # End signal

        task = asyncio.create_task(runner())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/minima/query")
async def minima_query(request: MinimaQueryRequest):
    logger.debug(f"Received Minima query request: {request.query}")
    
    if not roo.is_minima_connected():
        logger.error("Minima not connected")
        return {"status": "error", "message": "Not connected to Minima server"}
    
    try:
        logger.debug("Calling Minima tool with query")
        start_time = time.time()
        result = await roo.minima_adapter.call_tool("query", {"text": request.query})
        end_time = time.time()
        logger.debug(f"Minima query completed in {end_time - start_time:.2f} seconds")
        logger.debug(f"Minima query result: {result}")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error in Minima query: {str(e)}")
        return {"status": "error", "message": f"Error querying Minima: {str(e)}"}

@app.get("/minima/status")
async def minima_status():
    return {
        "status": "ok",
        "connected": roo.is_minima_connected(),
        "tools_count": len(roo.minima_tools) if roo.is_minima_connected() else 0,
        "tools": [tool["function"]["name"] for tool in roo.minima_tools] if roo.is_minima_connected() else []
    }

@app.get("/minima/connect")
async def connect_minima():
    try:
        if await roo.connect_to_minima():
            return {"status": "ok", "message": "Connected to Minima server"}
        else:
            return {"status": "error", "message": "Could not connect to Minima server"}
    except Exception as e:
        return {"status": "error", "message": f"Error connecting to Minima: {str(e)}"}

@app.get("/sessions")
async def get_sessions():
    """
    Retrieve all available sessions with their metadata.
    """
    # Create session entries for any histories that don't have metadata
    for session_id in histories:
        if session_id not in sessions:
            sessions[session_id] = {
                "id": session_id,
                "created_at": time.time() * 1000  # current time in milliseconds
            }
    
    # Return sessions sorted by creation time (newest first)
    sorted_sessions = sorted(
        sessions.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )
    
    return {"sessions": sorted_sessions}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and its associated history.
    """
    if session_id in sessions:
        del sessions[session_id]
        if session_id in histories:
            del histories[session_id]
        return {"status": "ok"}
    else:
        return {"status": "error", "message": "Session ID not found"}

@app.get("/clear-history")
async def clear_history(session_id: str):
    if session_id in histories:
        histories[session_id].clear()
        if session_id in sessions:
            del sessions[session_id]
        return {"status": "ok"}
    else:
        return {"status": "error", "message": "Session ID not found"}

@app.get("/chat-history")
async def get_chat_history(session_id: str):
    """
    Retrieve the chat history for a given session ID.
    """
    if session_id in histories:
        return {"status": "ok", "history": histories[session_id]}
    else:
        return {"status": "error", "message": "Session ID not found"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/tools")
async def list_tools():
    """List all available tools"""
    try:
        tools = roo.bridge.tool_registry.all_tools()
        tool_list = [
            {
                "name": tool.name,
                "description": tool.description,
                "adapter": tool.adapter_name,
                "emoji": tool.emoji
            }
            for tool in tools
        ]
        return {"status": "ok", "tools": tool_list, "count": len(tool_list)}
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return {"status": "error", "message": f"Error listing tools: {str(e)}"}

async def refresh_token_if_needed():
    """Check if GitHub token needs refresh and update it"""
    if "gh_auth_object" in config:
        auth = config["gh_auth_object"]
        # Get a fresh token (will use cached token if still valid)
        fresh_token = auth.get_token()
        if fresh_token != config.get("gh_token"):
            config["gh_token"] = fresh_token
            logger.debug("Refreshed GitHub token")

def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

@app.get("/port-info")
async def get_port_info():
    """Get information about the current port"""
    return {
        "port": os.getenv("PORT", "8000"),
        "host": os.getenv("HOST", "0.0.0.0")
    }

if __name__ == "__main__":
    import uvicorn
    
    # Write port to a file for the frontend to read
    port_file = Path(__file__).parent.parent / "frontend" / "port.json"
    port_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    with open(port_file, "w") as f:
        json.dump({"port": PORT}, f)
    
    logger.debug(f"Server starting on port {PORT}")
    logger.debug(f"Port info written to {port_file}")
    
    # Use workers=1 for better signal handling
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)