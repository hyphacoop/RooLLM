import os
import sys
import getpass
import asyncio
import json
import base64
from dotenv import load_dotenv

# Set up UTF-8 encoding for stdin
sys.stdin.reconfigure(encoding='utf-8')
from roollm import (RooLLM, ROLE_USER, make_ollama_inference)

# Load gh token from .env
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
ENCODED_GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", None)

"""
This script allows local testing of the RooLLM class.
You can chat with RooLLM in a terminal session.
Google credentials consists of a base64 encoded JSON object.

Usage:
1. Create an .env file in the roollm directory with the following content:
    
    ROO_LLM_AUTH_USERNAME=
    ROO_LLM_AUTH_PASSWORD=
    GITHUB_TOKEN=
    GOOGLE_CREDENTIALS=

    Ask the RooLLM team for the credentials.

2. Run this script to start the REPL.
"""
if ENCODED_GOOGLE_CREDENTIALS:
    DECODED_GOOGLE_CREDENTIALS = json.loads(base64.b64decode(ENCODED_GOOGLE_CREDENTIALS).decode())

config = {
    "gh_token": GITHUB_TOKEN,
    "google_creds": DECODED_GOOGLE_CREDENTIALS
    }
inference = make_ollama_inference()
roo = RooLLM(inference, config=config)
history = []

# Try to get the current login, otherwise fall back
try:
    user = os.getlogin()
except OSError:
    # Fallback if no controlling terminal (e.g., in Docker or a service)
    user = getpass.getuser() or "localTester"


# Define the callback to print emoji reactions
async def print_emoji_reaction(emoji):
    print(f"> tool call: {emoji}")


async def main():
    while True:
        query = input(">")
        response = await roo.chat(
            user,
            query, 
            history,
            react_callback=print_emoji_reaction
        )
            
        # Print the response content when working locally
        print(response['content'])

        history.append({
            'role': ROLE_USER,
            'content': user + ': ' + query
        })
        history.append(response)

asyncio.run(main())
