import aiohttp
import asyncio
import json
import os
import importlib
import time
from datetime import datetime
from dotenv import load_dotenv

try:
    from .tools import Tools
    from .stats import log_llm_usage
except ImportError:
    from tools import Tools
    from stats import log_llm_usage
# Load environment variables from .env
load_dotenv()

DEFAULT_OLLAMA_URL = os.getenv("ROO_LLM_URL", "https://ai.hypha.coop/api/chat")
DEFAULT_MODEL = os.getenv("ROO_LLM_MODEL", "hermes3")
DEFAULT_USERNAME = os.getenv("ROO_LLM_AUTH_USERNAME", "")
DEFAULT_PASSWORD = os.getenv("ROO_LLM_AUTH_PASSWORD", "")
DEFAULT_TOOL_LIST = ["calc", "search_handbook", "get_upcoming_holiday", "github_issues_operations", "github_pull_requests_operations", "get_upcoming_vacations", "fetch_remaining_vacation_days", "get_archive_categories"]

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"


class RooLLM:
    def __init__(self, inference, tool_list=DEFAULT_TOOL_LIST, config=None):
        self.inference = inference
        self.config = config or {}
        self.tools = Tools()
        for name in tool_list:
            self.tools.load_tool(name)

    async def chat(self, user, content, history=[], limit_tools=None, react_callback=None):
        system_message = make_message(ROLE_SYSTEM, self.make_system())
        user_message = make_message(ROLE_USER, user + ': ' + content)
        messages = [system_message, *history, user_message]

        tools = self.tools
        if limit_tools:
            tools = tools.subset(limit_tools)

        tool_descriptions = tools.descriptions()

        # measuring response time
        start_time = time.monotonic()

        # **Log LLM invocation**
        log_llm_usage(user=user)

        response = await self.inference(messages, tool_descriptions)

        while 'tool_calls' in response:
            messages.append(response)
            for call in response["tool_calls"]:
                if not 'function' in call:
                    continue
                func = call['function']
                tool_name = func['name']
                sub_tool_name = None 

                # Fetch the primary tool's emoji and react
                top_level_emoji = tools.get_tool_emoji(tool_name=tool_name)
                if top_level_emoji and react_callback:
                    await react_callback(top_level_emoji)  # First emoji reaction

                # Call the tool and store the result
                result = await tools.call(self, tool_name, func['arguments'], user)

                # If a GitHub dispatcher tool is used, react to the sub-tool as well
                if tool_name in ["github_issues_operations", "github_pull_requests_operations"]:
                    # Dynamically import ACTION_TO_TOOL from the corresponding module
                    try:
                        module_name = f"tools.{tool_name}"
                        module = importlib.import_module(module_name)
                        action_to_tool_map = getattr(module, "ACTION_TO_TOOL", {})
                    except ImportError:
                        action_to_tool_map = {}

                    action = func["arguments"].get("action")
                    if action:
                        sub_tool_name = action_to_tool_map.get(action)  # Map to sub-tool
                        if sub_tool_name:
                            sub_tool_emoji = tools.get_tool_emoji(tool_name=sub_tool_name)
                            if sub_tool_emoji and react_callback:
                                await react_callback(sub_tool_emoji)  # Second emoji reaction


                # Append response from tool execution
                messages.append(make_message(ROLE_TOOL, json.dumps(result)))
            response = await self.inference(messages, tool_descriptions)

        response_time = time.monotonic() - start_time  

        # Log usage
        log_llm_usage(
            user=user,
            tool_used=tool_name,
            subtool_used=sub_tool_name,
            response_time=response_time
        )

        return response

    def make_system(self):
        current_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""Your name is Roo also known as LifeForm168.
You are a cheerful AI assistant that works for the Hypha Worker Coop.
You sometimes use emoji at the end of your messages to add flavor to your text.
Avoid using the 🎉 emoji.
Hypha works with distributed systems, blockchains, and the intersection between art and technology.
You are currently chatting with the member members of Hypha.
Each message starts with the name of the user that wrote it.
You give short and concise responses.
You use tools to answer questions when needed.
The current date and time is {current_date_time}.
"""


def make_ollama_inference(
        url=DEFAULT_OLLAMA_URL,
        model=DEFAULT_MODEL,
        username=DEFAULT_USERNAME,
        password=DEFAULT_PASSWORD):

    async def inference(messages, tools=None, extra_options=None):
        payload = {
            "model": model,
            "stream": False,
            "messages": messages
        }
        if tools:
            payload["tools"] = tools

        if extra_options:
            payload.update(extra_options)

        response = await fetch(url, payload, username, password)

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
