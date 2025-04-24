import time
from datetime import datetime
import json
import pkgutil
import pathlib

try: 
    from .bridge import MCPLLMBridge
    from .tool_registry import ToolRegistry
    from .stats import log_llm_usage
except ImportError:
    from bridge import MCPLLMBridge
    from tool_registry import ToolRegistry
    from stats import log_llm_usage


ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"


def make_message(role, content):
    return {
        "role": role,
        "content": content
    }

class RooLLM:
    def __init__(self, inference, config=None):
            self.inference = inference
            self.config = config or {}
            self.tool_registry = ToolRegistry()

            self.bridge = MCPLLMBridge(
                llm_client=inference,
                config=config,
                tool_registry=self.tool_registry,
                roollm=self
            )

    async def chat(self, user, content, history=[], react_callback=None):
        system_message = make_message(ROLE_SYSTEM, self.make_system())
        user_message = make_message(ROLE_USER, f"{user}: {content}")
        messages = [system_message, *history, user_message]

        start_time = time.monotonic()

        response = await self.bridge.process_message(
            user=user,
            content=content,
            history=messages,
            react_callback=react_callback
        )

        response_time = time.monotonic() - start_time

        # optional: log it
        try:
            log_llm_usage(
                user=user,
                tool_used=response.get("tool_name"),
                subtool_used=response.get("sub_tool_name"),
                response_time=response_time
            )
        except Exception:
            pass 

        return response


    def update_config(self, new_config):
        self.config.update(new_config)

    def make_system(self):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""Your name is Roo, also known as LifeForm168.
You are an AI assistant created by and for the Hypha Worker Coop.

Hypha works on distributed systems, blockchains, governance, and open protocols in support of cooperative and community-led futures.

You assist Hypha members with research, coordination, writing, knowledge management, and technical problem-solving.

Respond concisely and clearly.
Use emoji sparingly, only at the end of your messages to add tone. Never use the 🎉 emoji.

Messages from users begin with their name followed by a colon.
You do not need to repeat their name in your replies.

You have access to tools. 
When a user asks for information that requires searching documents, calculating results, or checking external data, use the appropriate tool.

The current date and time is {now}.
"""
