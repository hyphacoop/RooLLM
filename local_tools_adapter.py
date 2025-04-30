import logging
from typing import Dict, Any, List, Optional
import importlib.util
import importlib.resources
import os
import sys
import pathlib
import traceback

# Add the parent directory to sys.path to allow relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

logger = logging.getLogger(__name__)

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
        
        # Find the tools directory
        self.current_file = __file__
        self.is_development = 'repl.py' in sys.argv[0] if sys.argv else False
        logger.info(f"Running in development mode: {self.is_development}")
        
        if self.is_development:
            # In development, use the direct filesystem path
            self.tools_dir = pathlib.Path(self.current_file).parent / "tools"
            logger.info(f"Using development tools directory: {self.tools_dir}")
        else:
            # In production, try to use importlib.resources
            logger.info("Attempting to find tools directory in production mode")
            try:
                with importlib.resources.path('hyphadevbot.roollm.tools', '__init__.py') as tools_path:
                    self.tools_dir = tools_path.parent
                    logger.info(f"Found tools directory using importlib.resources: {self.tools_dir}")
            except Exception as e:
                logger.warning(f"Could not find tools directory using importlib.resources: {e}")
                # Fallback to relative path
                self.tools_dir = pathlib.Path(self.current_file).parent / "tools"
                logger.info(f"Using fallback tools directory: {self.tools_dir}")
        
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
            self.connected = False
            return False
    
    def _load_tools(self) -> List[Tool]:
        """
        Load local tools from the tools directory.
        
        Returns:
            List of Tool objects
        """
        tools = []
        
        # Check if tools directory exists
        if not self.tools_dir.exists():
            logger.error(f"Tools directory does not exist: {self.tools_dir}")
            return tools
            
        # List available tool files for logging
        tool_files = list(self.tools_dir.glob("*.py"))
        logger.info(f"Found {len(tool_files)} potential tool files in {self.tools_dir}")
        
        # Load tools based on environment
        if self.is_development:
            # In development, use direct file loading
            logger.info(f"Loading tools from development directory: {self.tools_dir}")
            
            for path in tool_files:
                tool = self._load_tool_from_path(path)
                if tool:
                    tools.append(tool)
                    
        else:
            # In production, try importlib.resources first
            logger.info("Attempting to load tools using importlib.resources")
            
            try:
                with importlib.resources.path('hyphadevbot.roollm.tools', '__init__.py') as tools_path:
                    tools_dir = tools_path.parent
                    logger.info(f"Found tools directory in package: {tools_dir}")
                    
                    for path in tools_dir.glob("*.py"):
                        tool = self._load_tool_from_path(path, module_prefix="hyphadevbot.roollm.tools.")
                        if tool:
                            tools.append(tool)
                            
            except Exception as e:
                logger.error(f"Error loading tools using importlib.resources: {e}")
                logger.info("Falling back to direct file loading")
                
                for path in tool_files:
                    tool = self._load_tool_from_path(path)
                    if tool:
                        tools.append(tool)

        logger.info(f"Successfully loaded {len(tools)} local tools")
        
        # Log details of loaded tools
        for tool in tools:
            logger.info(f"Loaded tool: {tool.name} (Emoji: {tool.emoji})")
            
        return tools
    
    def _load_tool_from_path(self, path: pathlib.Path, module_prefix: str = "") -> Optional[Tool]:
        """
        Load a single tool from a Python file path.
        
        Args:
            path: Path to the Python file
            module_prefix: Prefix for the module name
            
        Returns:
            Tool object if successfully loaded, None otherwise
        """
        if path.name.startswith("_"):
            return None
            
        try:
            logger.debug(f"Attempting to load tool from: {path}")
            module_name = f"{module_prefix}{path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            
            if not spec:
                logger.warning(f"Could not create spec for {path}")
                return None
                
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            if not hasattr(mod, "tool"):
                logger.warning(f"Module {path.stem} has no tool function")
                return None
                
            tool = Tool(
                name=getattr(mod, "name", path.stem),
                description=getattr(mod, "description", "No description."),
                input_schema=getattr(mod, "parameters", {"type": "object", "properties": {}}),
                adapter_name="local",
                run_fn=self._wrap_tool(mod.tool),
                emoji=getattr(mod, "emoji", None)
            )
            
            logger.debug(f"Successfully loaded tool: {path.stem}")
            return tool
            
        except Exception as e:
            logger.error(f"Error loading module {path.stem}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
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