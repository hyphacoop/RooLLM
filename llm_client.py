import aiohttp
import os
import json
from typing import Optional

class LLMClient:
    def __init__(self, base_url: str, model: str, username: str = "", password: str = "", stream: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.auth = aiohttp.BasicAuth(username, password) if username and password else None
        self.stream = stream

    async def invoke(self, messages: list, tools: Optional[list] = None, extra_options: Optional[dict] = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": self.stream
        }

        if tools:
            payload["tools"] = tools

        if extra_options:
            payload.update(extra_options)

        url = f"{self.base_url}/api/chat"

        async with aiohttp.ClientSession(auth=self.auth) as session:
            async with session.post(url, json=payload) as response:
                body = await response.text()
                if response.status == 200:
                    return json.loads(body)
                raise Exception(f"LLMClient Error: {response.status} - {body}") 