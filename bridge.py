from typing import Dict, List
import json
import importlib

try:
    from .llm_client import LLMClient
    from .tool_registry import ToolRegistry, Tool
    from .mcp_client import MCPClient
except ImportError:
    from llm_client import LLMClient
    from tool_registry import ToolRegistry, Tool
    from mcp_client import MCPClient


def resolve_adapter_path(path: str) -> str:
    if not path.startswith("."):
        return path
    root = __name__.split(".")[0]
    return f"{root}{path[1:]}"

def load_adapter_from_config(name: str, conf: dict, full_config: dict):
    mode = conf.get("mode", "inline")

    if mode == "subprocess":
        return MCPClient(
            name=name,
            command=conf["command"],
            args=conf["args"],
            env=conf.get("env", {})
        )

    adapter_path = resolve_adapter_path(conf["env"]["MCP_ADAPTER"])
    mod_name, class_name = adapter_path.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    adapter_cls = getattr(mod, class_name)
    return adapter_cls(config=full_config)


class MCPLLMBridge:
    def __init__(self, config: Dict, llm_client: LLMClient, tool_registry=None, roollm=None):
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry or ToolRegistry()
        self.roollm = roollm
        self.mcp_clients: Dict[str, object] = {}

    async def initialize(self):
        mcp_configs = self.config.get("mcp_adapters", {})
        for name, adapter_conf in mcp_configs.items():
            adapter = load_adapter_from_config(name, adapter_conf, self.config)
            await adapter.connect()
            tools = await adapter.list_tools()
            for tool_dict in tools:
                # Wrap tool dict into Tool object expected by the registry
                tool_obj = Tool.from_dict(tool_dict, adapter_name=name)
                self.tool_registry.register_tool(tool_obj)
            self.mcp_clients[name] = adapter

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
