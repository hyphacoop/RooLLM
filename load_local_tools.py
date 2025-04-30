import importlib.util
import pathlib
import logging
import os
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tool_registry import Tool
except ImportError:
    from tool_registry import Tool

# Get the tools directory relative to this file
current_file = __file__
logger.debug(f"Current file path: {current_file}")

# Try multiple possible locations for tools
possible_tool_dirs = [
    pathlib.Path(current_file).parent / "tools",  # Original location
    pathlib.Path(os.path.dirname(current_file)) / "tools",  # Zip case
    pathlib.Path(os.path.dirname(os.path.dirname(current_file))) / "roollm" / "tools",  # One level up
]

# Find the first directory that exists and contains .py files
TOOLS_DIR = None
for dir_path in possible_tool_dirs:
    if dir_path.exists() and any(dir_path.glob("*.py")):
        TOOLS_DIR = dir_path
        break

if TOOLS_DIR is None:
    logger.error("Could not find tools directory in any of these locations:")
    for dir_path in possible_tool_dirs:
        logger.error(f"  - {dir_path}")
    TOOLS_DIR = possible_tool_dirs[0]  # Fallback to first option
    logger.warning(f"Using fallback tools directory: {TOOLS_DIR}")

logger.debug(f"Using tools directory: {TOOLS_DIR}")

def load_local_tools(config=None, roo=None) -> List[Tool]:
    """Load local tools from the tools directory.
    
    Args:
        config: Optional configuration dictionary
        roo: Optional RooLLM instance
        
    Returns:
        List of Tool objects
    """
    tools = []

    if not TOOLS_DIR.exists():
        logger.error(f"Tools directory does not exist: {TOOLS_DIR}")
        return tools

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue

        try:
            logger.debug(f"Attempting to load tool from: {path}")
            module_name = f"tools.{path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if not spec:
                logger.warning(f"Could not create spec for {path}")
                continue

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "tool"):
                logger.warning(f"Module {path.stem} has no tool function")
                continue

            tools.append(Tool(
                name=getattr(mod, "name", path.stem),
                description=getattr(mod, "description", "No description."),
                input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
                adapter_name="local",
                run_fn=wrap_tool(mod.tool),
                emoji=getattr(mod, "emoji", None)
            ))
            logger.debug(f"Successfully loaded tool: {path.stem}")
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
