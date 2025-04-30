import importlib.util
import pathlib
import logging
import os
import importlib.resources
import sys
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

try:
    from .tool_registry import Tool
except ImportError:
    from tool_registry import Tool

# Get the tools directory relative to this file
current_file = __file__
logger.info(f"Current file path: {current_file}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version}")
logger.info(f"sys.path: {sys.path}")
logger.info(f"Working directory: {os.getcwd()}")

# Check if we're running in development mode (from repl.py)
is_development = 'repl.py' in sys.argv[0] if sys.argv else False
logger.info(f"Running in development mode: {is_development}")
logger.info(f"sys.argv: {sys.argv}")

if is_development:
    # In development, use the direct filesystem path
    TOOLS_DIR = pathlib.Path(current_file).parent / "tools"
    logger.info(f"Using development tools directory: {TOOLS_DIR}")
else:
    # In production, try to use importlib.resources
    logger.info("Attempting to find tools directory in production mode")
    try:
        with importlib.resources.path('hyphadevbot.roollm.tools', '__init__.py') as tools_path:
            TOOLS_DIR = tools_path.parent
            logger.info(f"Found tools directory using importlib.resources: {TOOLS_DIR}")
            logger.info(f"Tools directory exists: {TOOLS_DIR.exists()}")
            if TOOLS_DIR.exists():
                logger.info(f"Tools directory contents: {list(TOOLS_DIR.glob('*.py'))}")
    except Exception as e:
        logger.warning(f"Could not find tools directory using importlib.resources: {e}")
        # Fallback to relative path
        TOOLS_DIR = pathlib.Path(current_file).parent / "tools"
        logger.info(f"Using fallback tools directory: {TOOLS_DIR}")
        logger.info(f"Fallback directory exists: {TOOLS_DIR.exists()}")
        if TOOLS_DIR.exists():
            logger.info(f"Fallback directory contents: {list(TOOLS_DIR.glob('*.py'))}")

def load_local_tools(config=None, roo=None) -> List[Tool]:
    """Load local tools from the tools directory.
    
    Args:
        config: Optional configuration dictionary
        roo: Optional RooLLM instance
        
    Returns:
        List of Tool objects
    """
    tools = []
    logger.info(f"Starting to load tools in {'development' if is_development else 'production'} mode")

    if is_development:
        # In development, use direct file loading
        if not TOOLS_DIR.exists():
            logger.error(f"Tools directory does not exist: {TOOLS_DIR}")
            return tools

        logger.info(f"Loading tools from development directory: {TOOLS_DIR}")
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
                logger.info(f"Module {module_name} contents: {dir(mod)}")
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
    else:
        # In production, try importlib.resources first
        logger.info("Attempting to load tools using importlib.resources")
        try:
            with importlib.resources.path('hyphadevbot.roollm.tools', '__init__.py') as tools_path:
                tools_dir = tools_path.parent
                logger.info(f"Found tools directory in zip: {tools_dir}")
                logger.info(f"Tools directory exists: {tools_dir.exists()}")
                if tools_dir.exists():
                    logger.info(f"Tools directory contents: {list(tools_dir.glob('*.py'))}")

                for path in tools_dir.glob("*.py"):
                    if path.name.startswith("_"):
                        continue

                    try:
                        logger.debug(f"Attempting to load tool from zip: {path}")
                        module_name = f"hyphadevbot.roollm.tools.{path.stem}"
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
                        logger.debug(f"Successfully loaded tool from zip: {path.stem}")
                    except Exception as e:
                        logger.error(f"Error loading module {path.stem} from zip: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error loading tools using importlib.resources: {e}")
            # Fallback to direct file loading
            logger.info("Falling back to direct file loading")
            if not TOOLS_DIR.exists():
                logger.error(f"Tools directory does not exist: {TOOLS_DIR}")
                return tools

            logger.info(f"Loading tools from fallback directory: {TOOLS_DIR}")
            for path in TOOLS_DIR.glob("*.py"):
                if path.name.startswith("_"):
                    continue

                try:
                    logger.debug(f"Attempting to load tool from fallback: {path}")
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
                    logger.debug(f"Successfully loaded tool from fallback: {path.stem}")
                except Exception as e:
                    logger.error(f"Error loading module {path.stem} from fallback: {e}")
                    continue

    logger.info(f"Loaded {len(tools)} local tools")
    return tools

def wrap_tool(func):
    """Wrap a tool function to ensure it's async and has the correct signature."""
    async def wrapper(roo, args, user):
        return await func(roo, args, user)
    return wrapper
