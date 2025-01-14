import os
import asyncio

from roollm import (RooLLM, ROLE_USER, make_ollama_inference)

inference = make_ollama_inference()
user = os.getlogin()
roo = RooLLM(inference)
history = []


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
