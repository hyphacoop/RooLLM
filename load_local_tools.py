import importlib.util
import pathlib
import logging
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tool_registry import Tool
    print("Loaded tool_registry from .tool_registry")
    TOOLS_DIR = ".roollm.tools"
    logger.debug(f"TOOLS_DIR: {TOOLS_DIR}")
except ImportError:
    from tool_registry import Tool
    print("Loaded tool_registry from tool_registry")
    TOOLS_DIR = pathlib.Path(__file__).parent / "tools"
    logger.debug(f"TOOLS_DIR: {TOOLS_DIR}")

def load_local_tools(config=None, roo=None):
    tools = []

    # Handle both module path string and filesystem path cases
    if isinstance(TOOLS_DIR, str):
        # Module path case - use importlib to get the module
        try:
            tools_module = importlib.import_module(TOOLS_DIR)
            for name in dir(tools_module):
                if name.startswith("_"):
                    continue
                try:
                    mod = importlib.import_module(f"{TOOLS_DIR}.{name}")
                    if not hasattr(mod, "tool"):
                        continue
                    
                    emoji = getattr(mod, "emoji", None)
                    logger.debug(f"Found tool: {name} with emoji: {emoji}")

                    tools.append(Tool(
                        name=getattr(mod, "name", name),
                        description=getattr(mod, "description", "No description."),
                        input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
                        adapter_name="local",
                        run_fn=wrap_tool(mod.tool),
                        emoji=emoji
                    ))
                except Exception as e:
                    logger.error(f"Error loading tool {name}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error loading tools module: {e}")
    else:
        # Filesystem path case - use the original file-based loading
        logger.debug(f"Loading tools from directory: {TOOLS_DIR}")
        logger.debug(f"Directory exists: {TOOLS_DIR.exists()}")
        logger.debug(f"Directory contents: {list(TOOLS_DIR.glob('*.py'))}")

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
                logger.error(f"Error loading module {path.stem}: {e}")
                continue

    logger.info(f"Loaded {len(tools)} tools")
    return tools

def wrap_tool(func):
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
