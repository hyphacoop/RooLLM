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
from contextlib import asynccontextmanager, suppress

# Port configuration
PORT = int(os.getenv("PORT", "8081"))
API_HOST = os.getenv("API_HOST", "localhost")

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
    password=os.getenv("ROO_LLM_AUTH_PASSWORD", ""),
    think=os.getenv("ROO_LLM_THINK", "true").lower() not in ("0", "false", "no"),
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

def get_minima_adapter():
    """Get the minima adapter from the bridge if available."""
    if not roo.bridge.initialized:
        return None
    return roo.bridge.mcp_clients.get("minima")

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
            user_message = f"{request.message}"
            streamed_parts = []
            saw_delta = False

            async def safe_stream_callback(delta):
                nonlocal saw_delta
                if not isinstance(delta, str) or not delta:
                    return
                saw_delta = True
                streamed_parts.append(delta)
                await queue.put({"type": "reply_delta", "content": delta})

            try:
                response = await roo.chat(
                    content=request.message,
                    history=history,
                    react_callback=safe_react_callback,
                    stream_callback=safe_stream_callback,
                )

                response_content = response.get("content", "")
                final_content = "".join(streamed_parts) if saw_delta else response_content

                # Ensure final content stays consistent even if fallback paths differ.
                if response_content and final_content != response_content:
                    if response_content.startswith(final_content):
                        tail = response_content[len(final_content):]
                        if tail:
                            final_content = response_content
                            await queue.put({"type": "reply_delta", "content": tail})
                    else:
                        final_content = response_content
                        saw_delta = False

                # Add to history with proper format
                history.append({"role": "user", "content": user_message})
                history.append({"role": "assistant", "content": final_content})
                histories[request.session_id] = history

                # Update initial prompt if this is the first message
                if len(history) == 2:  # Just added first user and assistant messages
                    sessions[request.session_id]["initial_prompt"] = generate_session_title(history)

                if saw_delta:
                    await queue.put({"type": "reply_done", "content": final_content})
                else:
                    # Backward-compatible fallback event
                    await queue.put({"type": "reply", "content": final_content})
            except Exception as e:
                logger.error(f"Error in chat stream runner: {e}", exc_info=True)
                await queue.put({
                    "type": "error",
                    "content": "I encountered an error while processing your request.",
                })
            finally:
                await queue.put(None)  # End signal

        task = asyncio.create_task(runner())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/minima/query")
async def minima_query(request: MinimaQueryRequest):
    logger.debug(f"Received Minima query request: {request.query}")

    adapter = get_minima_adapter()
    if not adapter or not adapter.is_connected():
        logger.error("Minima not connected")
        return {"status": "error", "message": "Not connected to Minima server"}

    try:
        logger.debug("Calling Minima tool with query")
        start_time = time.time()
        result = await adapter.call_tool("query", {"text": request.query})
        end_time = time.time()
        logger.debug(f"Minima query completed in {end_time - start_time:.2f} seconds")
        logger.debug(f"Minima query result: {result}")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error in Minima query: {str(e)}")
        return {"status": "error", "message": f"Error querying Minima: {str(e)}"}

@app.get("/minima/status")
async def minima_status():
    adapter = get_minima_adapter()
    connected = adapter.is_connected() if adapter else False
    tools = list(adapter.tools.values()) if connected else []
    return {
        "status": "ok",
        "connected": connected,
        "tools_count": len(tools),
        "tools": [tool.get("name") for tool in tools]
    }

@app.get("/minima/connect")
async def connect_minima():
    adapter = get_minima_adapter()
    if not adapter:
        return {"status": "error", "message": "Minima adapter not configured"}
    try:
        if await adapter.connect(force=True):
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

BRANDING_FILE = Path(os.getenv("BRANDING_CONFIG_PATH", "/etc/roollm/branding.json"))

@app.get("/branding")
async def get_branding():
    """Return tenant branding configuration."""
    try:
        if BRANDING_FILE.exists():
            return json.loads(BRANDING_FILE.read_text())
    except Exception as e:
        logger.error(f"Error reading branding config: {e}")
    return {}

async def refresh_token_if_needed():
    """Check if GitHub token needs refresh and update it"""
    if config.get("gh_auth_object"):
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
    """Get information about the current port and host"""
    return {
        "port": PORT,
        "host": API_HOST
    }

if __name__ == "__main__":
    import uvicorn
    
    # Write API configuration to a file for the frontend to read
    api_config_file = Path(__file__).parent.parent / "frontend" / "api_config.json"
    api_config_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    with open(api_config_file, "w") as f:
        json.dump({"port": PORT, "host": API_HOST}, f)

    logger.debug(f"Server starting on port {PORT}")
    logger.debug(f"API config written to {api_config_file}")
    
    # Use workers=1 for better signal handling
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
