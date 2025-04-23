from typing import Dict, List
import json

try:
    from .llm_client import LLMClient
    from .tool_registry import ToolRegistry
    from .mcp_client import MCPClient
except ImportError:
    from llm_client import LLMClient
    from tool_registry import ToolRegistry
    from mcp_client import MCPClient

class MCPLLMBridge:
    def __init__(self, config: Dict, llm_client: LLMClient, tool_registry=None, roollm=None):
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry or ToolRegistry()
        self.roollm = roollm
        self.mcp_clients: Dict[str, MCPClient] = {}

    async def initialize(self):
        mcp_configs = self.config.get("mcp_adapters", {})
        for name, adapter_conf in mcp_configs.items():
            client = MCPClient(
                name=name,
                command=adapter_conf["command"],
                args=adapter_conf["args"],
                env=adapter_conf.get("env", {})
            )
            await client.connect()
            tools = await client.list_tools()
            for tool in tools:
                self.tool_registry.register_tool(tool)
            self.mcp_clients[name] = client

    async def process_message(self, user: str, content: str, history: List[Dict], react_callback=None):
        messages = history + [{"role": "user", "content": f"{user}: {content}"}]
        tools = self.tool_registry.openai_descriptions()

        raw_response = await self.llm_client.invoke(messages, tools=tools)

        message = raw_response.get("message", {})

        if "tool_calls" not in message:
            return message  # no tool calls—just return

        messages.append(message)

        tool_outputs = []
        for call in message["tool_calls"]:
            func = call.get("function", {})
            name = func.get("name")
            args = func.get("arguments", {})
            tool_call_id = call.get("id", name)

            tool = self.tool_registry.get_tool(name)
            if not tool:
                continue

            if react_callback:
                await react_callback(tool.emoji or tool.name)

            if tool.adapter_name == "local" and tool.run_fn:
                result = await tool.run_fn(self.roollm, args, user)
            else:
                adapter = self.mcp_clients[tool.adapter_name]
                result = await adapter.call_tool(name, args)


            tool_outputs.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(result)
            })


        messages.extend(tool_outputs)


        final = await self.llm_client.invoke(messages, tools=tools)
        return final.get("message", {})
