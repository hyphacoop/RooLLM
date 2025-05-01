import logging
import pkgutil
import importlib
import pathlib
import traceback

from typing import Dict, Any, List, Optional
import sys

# Configure logging
logger = logging.getLogger(__name__)


logger.debug(f"sys.path: {sys.path}")
logger.debug(f"cwd: {pathlib.Path.cwd()}")
logger.debug(f"__package__: {__package__}")

# Import Tool class
try: 
    from .tool_registry import Tool
except ImportError:
    try:
        from tool_registry import Tool
    except ImportError as e:
        logger.error(f"Failed to import Tool class: {e}")
        raise


class LocalToolsAdapter:
    """
    Adapter that loads local tools and wraps them in the MCP interface.
    This class integrates both tool discovery and the adapter interface.
    """
    
    def __init__(self, config=None):
        """
        Initialize the local tools adapter.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.connected = False
        self.tools_metadata = {}  # Just the metadata for MCP interface
        self.tool_instances = {}  # Actual tool instances for execution
        self.roo = None  # Will be set by the bridge
        
    async def connect(self, force=False):
        """Connect to the local tools by loading them."""
        if self.connected and not force:
            return True
            
        try:
            # Load local tools
            local_tools = self._load_tools()
            
            # Store the tool instances for later use
            self.tool_instances = {tool.name: tool for tool in local_tools}
            
            # Convert tools to MCP format for metadata
            self.tools_metadata = {
                tool.name: {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "emoji": tool.emoji
                }
                for tool in local_tools
            }
            
            self.connected = True
            logger.info(f"Successfully loaded {len(self.tools_metadata)} local tools")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load local tools: {e}")
            logger.debug(traceback.format_exc())
            self.connected = False
            return False

    def _resolve_tools_package(self):
        # try the long path (maubot context)
        try:
            pkg = importlib.import_module("hyphadevbot.roollm.tools")
            logger.debug("Resolved tools package as 'hyphadevbot.roollm.tools'")
            return pkg
        except ImportError as e:
            logger.debug(f"Failed to import 'hyphadevbot.roollm.tools': {e}")

        # try short path (e.g., run from project root with PYTHONPATH=. or installed module)
        try:
            pkg = importlib.import_module("roollm.tools")
            logger.debug("Resolved tools package as 'roollm.tools'")
            return pkg
        except ImportError as e:
            logger.debug(f"Failed to import 'roollm.tools': {e}")

        # try local relative import via package context
        if __package__:
            try:
                pkg = importlib.import_module(".tools", package=__package__)
                logger.debug(f"Resolved tools package as relative '.tools' from {__package__}")
                return pkg
            except ImportError as e:
                logger.debug(f"Failed relative import '.tools': {e}")

        raise ImportError("Could not resolve tools package — check PYTHONPATH or working directory.")

    def _load_tools(self) -> List[Tool]:
        tools = []
        try:
            tools_pkg = self._resolve_tools_package()
            tools_pkg_name = tools_pkg.__name__
            for _, modname, _ in pkgutil.iter_modules(tools_pkg.__path__):
                if modname.startswith("_"):
                    continue
                full_modname = f"{tools_pkg_name}.{modname}"
                try:
                    mod = importlib.import_module(full_modname)
                    if not hasattr(mod, "tool"):
                        logger.warning(f"Module {modname} has no tool function")
                        continue
                    tool = Tool(
                        name=getattr(mod, "name", modname),
                        description=getattr(mod, "description", "No description."),
                        input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
                        adapter_name="local",
                        run_fn=self._wrap_tool(mod.tool),
                        emoji=getattr(mod, "emoji", None)
                    )
                    tools.append(tool)
                    logger.info(f"Loaded tool: {tool.name} (Emoji: {tool.emoji})")
                except Exception as e:
                    logger.error(f"Failed to import tool module {full_modname}: {e}")
                    logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error(f"Failed to resolve tools package: {e}")
            logger.debug(traceback.format_exc())
        return tools
    
    def _wrap_tool(self, func):
        """Wrap a tool function to ensure it's async and has the correct signature."""
        async def wrapper(roo, args, user):
            try:
                return await func(roo, args, user)
            except Exception as e:
                logger.error(f"Error executing tool function: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                return {"error": f"Tool execution failed: {str(e)}"}
        return wrapper
            
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get the list of available local tools."""
        if not self.connected:
            await self.connect()
            
        return list(self.tools_metadata.values())
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific local tool with the given arguments."""
        if not self.connected:
            await self.connect()
        
        # Use the cached tool instance
        tool = self.tool_instances.get(tool_name)
        
        if not tool or not tool.run_fn:
            logger.error(f"Tool {tool_name} not found or has no run function")
            raise ValueError(f"Tool {tool_name} not found or has no run function")
            
        # Call the tool's run function with the roo instance
        try:
            return await tool.run_fn(self.roo, arguments, "mcp")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}