import importlib.util
import pathlib
import logging
from typing import List
import os

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tool_registry import Tool
    print("Loaded tool_registry from .tool_registry")
except ImportError:
    from tool_registry import Tool
    print("Loaded tool_registry from tool_registry")

# Get the base directory - either from __file__ in dev or from plugin root in maubot
try:
    # Try to get the plugin directory from maubot
    from maubot import Plugin
    plugin = Plugin.get_instance()
    BASE_DIR = pathlib.Path(plugin.directory)
    logger.debug(f"Running as maubot plugin. Plugin directory: {BASE_DIR}")
except (ImportError, AttributeError) as e:
    # We're running in development
    BASE_DIR = pathlib.Path(__file__).parent
    logger.debug(f"Running in development mode. Base directory: {BASE_DIR}")
    logger.debug(f"Import error details: {str(e)}")

TOOLS_DIR = BASE_DIR / "tools"
logger.debug(f"TOOLS_DIR: {TOOLS_DIR}")
logger.debug(f"TOOLS_DIR absolute path: {TOOLS_DIR.absolute()}")
logger.debug(f"TOOLS_DIR exists: {TOOLS_DIR.exists()}")
logger.debug(f"TOOLS_DIR is directory: {TOOLS_DIR.is_dir()}")
logger.debug(f"Parent directory contents: {list(BASE_DIR.iterdir())}")

def load_local_tools(config=None, roo=None):
    tools = []

    logger.debug(f"Loading tools from directory: {TOOLS_DIR}")
    logger.debug(f"Directory exists: {TOOLS_DIR.exists()}")
    logger.debug(f"Directory contents: {list(TOOLS_DIR.glob('*.py'))}")

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("_"):
            logger.debug(f"Skipping hidden file: {path.name}")
            continue

        try:
            module_name = f"tools.{path.stem}"
            logger.debug(f"Loading module: {module_name} from {path}")
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if not spec:
                logger.debug(f"No spec found for {module_name}")
                continue

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "tool"):
                logger.debug(f"Module {module_name} has no tool attribute")
                continue

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
        except Exception as e:
            logger.error(f"Error loading module {path.stem}: {e}", exc_info=True)
            continue

    logger.info(f"Loaded {len(tools)} tools")
    return tools

def wrap_tool(func):
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
