import os
import getpass
import asyncio

from roollm import (RooLLM, ROLE_USER, make_ollama_inference)

"""
This script allows local testing of the RooLLM class.
You can chat with RooLLM in a terminal session.

Usage:
1. Create an .env file in the roollm directory with the following content:
    
    ROO_LLM_AUTH_USERNAME=
    ROO_LLM_AUTH_PASSWORD=

    Ask the RooLLM team for the credentials.

2. Run this script to start the REPL.
"""

inference = make_ollama_inference()
roo = RooLLM(inference)
history = []

# Try to get the current login, otherwise fall back
try:
    user = os.getlogin()
except OSError:
    # Fallback if no controlling terminal (e.g., in Docker or a service)
    user = getpass.getuser() or "localTester"


async def main():
    while True:
        query = input(">")
        response, emojis = await roo.chat(user, query, history)

        for emoji in emojis:
            print(f"Tool called: {emoji}")
            
        # Print the response content when working locally
        print(response['content'])

        history.append({
            'role': ROLE_USER,
            'content': user + ': ' + query
        })
        history.append(response)

asyncio.run(main())
