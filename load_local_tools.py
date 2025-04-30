import importlib.util
import pathlib
import logging
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tool_registry import Tool
except ImportError:
    from tool_registry import Tool

# Get the tools directory relative to this file
TOOLS_DIR = pathlib.Path(__file__).parent / "tools"

def load_local_tools(config=None, roo=None) -> List[Tool]:
    """Load local tools from the tools directory.
    
    Args:
        config: Optional configuration dictionary
        roo: Optional RooLLM instance
        
    Returns:
        List of Tool objects
    """
    tools = []

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue

        try:
            module_name = f"tools.{path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if not spec:
                continue

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "tool"):
                continue

            tools.append(Tool(
                name=getattr(mod, "name", path.stem),
                description=getattr(mod, "description", "No description."),
                input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
                adapter_name="local",
                run_fn=wrap_tool(mod.tool),
                emoji=getattr(mod, "emoji", None)
            ))
            logger.debug(f"Loaded tool: {path.stem}")
        except Exception as e:
            logger.error(f"Error loading module {path.stem}: {e}")
            continue

    logger.info(f"Loaded {len(tools)} local tools")
    return tools

def wrap_tool(func):
    """Wrap a tool function to ensure it's async and has the correct signature."""
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
