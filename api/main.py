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


# Add parent directory to path to import roollm
sys.path.append(str(Path(__file__).parent.parent))

# Import roollm
from roollm import RooLLM, ROLE_USER, ROLE_ASSISTANT, make_ollama_inference
from roollm_with_minima import make_roollm_with_minima
from github_app_auth import prepare_github_token

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitHub Setup
gh_config = {
    "GITHUB_APP_ID": os.getenv("GITHUB_APP_ID"),
    "GITHUB_PRIVATE_KEY": base64.b64decode(os.getenv("GITHUB_PRIVATE_KEY_BASE64", "")).decode('utf-8') if os.getenv("GITHUB_PRIVATE_KEY_BASE64") else None,
    "GITHUB_INSTALLATION_ID": os.getenv("GITHUB_INSTALLATION_ID"),
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
}

github_token, auth_method, auth_object = prepare_github_token(gh_config)

# Google Setup
google_creds = None
if creds := os.getenv("GOOGLE_CREDENTIALS"):
    google_creds = json.loads(base64.b64decode(creds).decode())

# Minima Setup
USE_MINIMA = os.getenv("USE_MINIMA_MCP", "false").lower() == "true"
MINIMA_SERVER_URL = os.getenv("MINIMA_MCP_SERVER_URL", "http://localhost:8000")

# LLM Setup
config = {
    "gh_token": github_token,
    "gh_auth_object": auth_object,
    "google_creds": google_creds
}
inference = make_ollama_inference()
roo = make_roollm_with_minima(inference, config=config)

# App & State
app = FastAPI()

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
        if message.get('role') == ROLE_USER:
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
            response = await roo.chat(
                user,
                request.message,
                history,
                react_callback=safe_react_callback
            )

            # Add to history
            history.append({'role': ROLE_USER, 'content': request.message})
            history.append({'role': ROLE_ASSISTANT, 'content': response["content"]})
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
    logger.info(f"Received Minima query request: {request.query}")
    
    if not roo.is_minima_connected():
        logger.error("Minima not connected")
        return {"status": "error", "message": "Not connected to Minima server"}
    
    try:
        logger.info("Calling Minima tool with query")
        start_time = time.time()
        result = await roo.minima_adapter.call_tool("query", {"text": request.query})
        end_time = time.time()
        logger.info(f"Minima query completed in {end_time - start_time:.2f} seconds")
        logger.info(f"Minima query result: {result}")
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

async def refresh_token_if_needed():
    if auth_object:
        fresh_token = auth_object.get_token()
        if fresh_token != config.get("gh_token"):
            config["gh_token"] = fresh_token
            roo.update_config({"gh_token": fresh_token})
            logger.info("Refreshed GitHub token")

# Global variable for port
current_port = None

# Function to find an available port
def find_available_port(start_port, max_attempts=10):
    port = start_port
    for _ in range(max_attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except socket.error:
            port += 1
        finally:
            sock.close()
    # If no ports are available in the range, return None or raise an exception
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port+max_attempts-1}")

# Add an endpoint to provide port information to the frontend
@app.get("/port-info")
async def get_port_info():
    return {"port": current_port}

if __name__ == "__main__":
    import uvicorn
    start_port = int(os.getenv("PORT", 8000))
    current_port = find_available_port(start_port)
    
    # Write port to a file for the frontend to read
    port_file = Path(__file__).parent.parent / "frontend" / "port.json"
    with open(port_file, "w") as f:
        json.dump({"port": current_port}, f)
    
    logger.info(f"Server starting on port {current_port}")
    
    # Use workers=1 for better signal handling
    uvicorn.run("main:app", host="0.0.0.0", port=current_port, reload=True)
