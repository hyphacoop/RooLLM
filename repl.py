import os
import getpass
import asyncio
from dotenv import load_dotenv

from roollm import (RooLLM, ROLE_USER, make_ollama_inference)

# Load gh token from .env
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)

"""
This script allows local testing of the RooLLM class.
You can chat with RooLLM in a terminal session.

Usage:
1. Create an .env file in the roollm directory with the following content:
    
    ROO_LLM_AUTH_USERNAME=
    ROO_LLM_AUTH_PASSWORD=
    GITHUB_TOKEN=

    Ask the RooLLM team for the credentials.

2. Run this script to start the REPL.
"""

config = {"gh_token": GITHUB_TOKEN}
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
