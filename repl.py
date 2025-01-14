import os
import getpass
import asyncio

from roollm import (RooLLM, ROLE_USER, make_ollama_inference)

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
        response = await roo.chat(user, query, history)

        history.append({
            'role': ROLE_USER,
            'content': query
        })
        history.append(response)

asyncio.run(main())
