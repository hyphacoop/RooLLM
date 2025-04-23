import importlib.util
import pathlib
from typing import List

try:
    from .tool_registry import Tool
except ImportError:
    from tool_registry import Tool

TOOLS_DIR = pathlib.Path(__file__).parent / "tools"

def load_local_tools(config=None, roo=None):
    tools = []

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue  # skip __init__.py etc.

        module_name = f"tools.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, "tool"):
            continue  # must define `tool(...)`

        emoji = getattr(mod, "emoji", None)

        tools.append(Tool(
            name=getattr(mod, "name", path.stem),
            description=getattr(mod, "description", "No description."),
            input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
            adapter_name="local",
            run_fn=wrap_tool(mod.tool),
            emoji=emoji
        ))


    return tools

def wrap_tool(func):
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
