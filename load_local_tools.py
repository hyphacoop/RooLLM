import importlib.util
import pathlib
import logging
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tools.tool_registry import Tool
except ImportError:
    from tools.tool_registry import Tool

TOOLS_DIR = pathlib.Path(__file__).parent / "tools"

def load_local_tools(config=None, roo=None):
    tools = []

    logger.debug(f"Loading tools from directory: {TOOLS_DIR}")
    logger.debug(f"Directory exists: {TOOLS_DIR.exists()}")
    logger.debug(f"Directory contents: {list(TOOLS_DIR.glob('*.py'))}")

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue  # skip __init__.py etc.

        module_name = f"hyphadevbot.roollm.tools.{path.stem}"
        logger.debug(f"Loading module: {module_name} from {path}")
        
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, "tool"):
            logger.debug(f"Skipping {path.name} - no tool function found")
            continue  # must define `tool(...)`

        emoji = getattr(mod, "emoji", None)
        logger.debug(f"Found tool: {path.stem} with emoji: {emoji}")

        tools.append(Tool(
            name=getattr(mod, "name", path.stem),
            description=getattr(mod, "description", "No description."),
            input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
            adapter_name="local",
            run_fn=wrap_tool(mod.tool),
            emoji=emoji
        ))

    logger.info(f"Loaded {len(tools)} tools")
    return tools

def wrap_tool(func):
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
