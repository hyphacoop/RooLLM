import aiohttp
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from tools import Tools

# Load environment variables from .env
load_dotenv()

DEFAULT_OLLAMA_URL = os.getenv("ROO_LLM_URL", "https://ai.hypha.coop/api/chat")
DEFAULT_MODEL = os.getenv("ROO_LLM_MODEL", "hermes3")
DEFAULT_USERNAME = os.getenv("ROO_LLM_AUTH_USERNAME", "")
DEFAULT_PASSWORD = os.getenv("ROO_LLM_AUTH_PASSWORD", "")
DEFAULT_TOOL_LIST = ["calc", "search_handbook"]

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"


class RooLLM:
    def __init__(self, inference, tool_list=DEFAULT_TOOL_LIST):
        self.inference = inference
        self.tools = Tools()
        for name in tool_list:
            self.tools.load_tool(name)


    async def chat(self, user, content, history=[], limit_tools=None):
        system_message = make_message(ROLE_SYSTEM, self.make_system(user))
        user_message = make_message(ROLE_USER, content)
        messages = [system_message, *history, user_message]

        tools = self.tools
        if limit_tools:
            tools = tools.subset(limit_tools)

        tool_descriptions = tools.descriptions()

        # print(tool_descriptions)

        response = await self.inference(messages, tool_descriptions)

        while 'tool_calls' in response:
            messages.append(response)
            for call in response["tool_calls"]:
                if not 'function' in call:
                    continue
                func = call['function']
                result = await tools.call(self, func['name'], func['arguments'])
                messages.append(make_message(ROLE_TOOL, json.dumps(result)))
            response = await self.inference(messages, tool_descriptions)

        return response

    def make_system(self, user):
        current_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""Your name is Roo.
You are a cheerful AI assistant that works for the Hypha Worker Coop.
You sometimes use emoji to add flavor to your text.
Hypha works with distributed systems, blockchains, and the intersection between art and technology.
You are currently chatting with the member named {user}.
You give short and concise responses.
Use tools when needed.
The current date and time is {current_date_time}
"""


def make_ollama_inference(
        url=DEFAULT_OLLAMA_URL,
        model=DEFAULT_MODEL,
        username=DEFAULT_USERNAME,
        password=DEFAULT_PASSWORD):
    async def inference(messages, tools=None):
        payload = {
            "model": model,
            "stream": False,
            "messages": messages
        }
        if tools:
            payload["tools"] = tools

        response = await fetch(url, payload, username, password)

        # print(response)
        return response.get("message", make_message(ROLE_ASSISTANT, "Error: Unable to generate response"))

    return inference


async def fetch(url, payload, username, password):
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(username, password)) as session:
        async with session.post(
            url,
            json=payload
        ) as response:
            body = await response.text()

            if response.status == 200:
                result = json.loads(body)  # Parse the JSON response
                return result
            else:
                raise Exception(f"Error: {response.status} - {body}")


def make_message(role, content):
    return {
        'role': role,
        'content': content
    }
