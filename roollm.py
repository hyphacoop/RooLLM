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

The current date and time is {now}.

You have access to tools including:
- query: Use this tool when you need information about Hypha's policies, handbook content, processes, or documents stored in the public Google Drive
- get_upcoming_holiday: For holiday information
- get_upcoming_vacations: For information about who is currently on vacation
- calc: For calculations
- github_dispatcher: For GitHub operations

Guidelines for tool usage:
1. When a user asks about Hypha-specific information (policies, processes, documentation), use the query tool to search relevant documents
2. When using information from documents, include source citations in the format [Source: /path/to/document]
    - If the document is indexed from the handbook, use the format [Source: handbook.hypha.coop/path/to/document]
    - If the document is indexed from Hypha's public Google Drive, use the format [Source: Hypha Public Drive /path/to/document]
3. Only cite documents that were actually returned by the query tool
4. If the query tool doesn't return relevant information, clearly state that you don't have the specific information
5. For general knowledge questions unrelated to Hypha-specific content, respond directly without using the query tool
6. Use other specialized tools when appropriate (for vacations, GitHub operations, etc.)

Provide helpful, accurate responses based on available information. Don't make up or guess information that isn't available to you.
"""
