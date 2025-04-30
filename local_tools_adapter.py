import logging
from typing import Dict, Any, List, Optional
import importlib.util
import os
import sys
import pathlib
import traceback
import inspect

# Configure logging
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
        
        # Find the tools directory with improved path handling for maubot
        self._find_tools_directory()
        
    def _find_tools_directory(self):
        """Find the tools directory using multiple fallback methods."""
        # Log current working directory and sys.path for debugging
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.debug(f"sys.path: {sys.path}")
        
        # Method 1: Check for environment variable (highest priority)
        if tools_dir_env := os.environ.get("ROOLLM_TOOLS_DIR"):
            self.tools_dir = pathlib.Path(tools_dir_env)
            logger.info(f"Using tools directory from environment: {self.tools_dir}")
            if self.tools_dir.exists() and any(self.tools_dir.glob("*.py")):
                return
            else:
                logger.warning(f"Tools directory from environment variable does not exist or has no Python files: {self.tools_dir}")

        # Method 2: Use the file location of this module
        try:
            # Get the directory containing this file
            current_file = inspect.getfile(self.__class__)
            module_dir = pathlib.Path(current_file).parent
            logger.debug(f"Module directory: {module_dir}")
            
            # Look for ./tools relative to this file
            self.tools_dir = module_dir / "tools"
            logger.info(f"Looking for tools in: {self.tools_dir}")
            
            # Verify this directory exists and has Python files
            if self.tools_dir.exists() and any(self.tools_dir.glob("*.py")):
                logger.info(f"Found tools directory at {self.tools_dir}")
                return
            else:
                logger.warning(f"Tools directory not found or has no Python files at {self.tools_dir}")
        except Exception as e:
            logger.warning(f"Error finding tools directory relative to module: {e}")
            
        # Method 3: Try finding the tools directory in plugin directories (maubot specific)
        try:
            # Look for tools in the plugin paths from sys.path
            for path in sys.path:
                if ('plugins' in path or 'hyphadevbot' in path):
                    logger.debug(f"Checking potential plugin path: {path}")
                    
                    # Common patterns in maubot plugin structure
                    candidate_paths = [
                        pathlib.Path(path) / "roollm" / "tools",
                        pathlib.Path(path) / "tools",
                        # Go up one level and check
                        pathlib.Path(path).parent / "roollm" / "tools"
                    ]
                    
                    for candidate in candidate_paths:
                        logger.debug(f"Checking candidate path: {candidate}")
                        if candidate.exists() and any(candidate.glob("*.py")):
                            self.tools_dir = candidate
                            logger.info(f"Found tools directory in plugin path: {self.tools_dir}")
                            return
        except Exception as e:
            logger.warning(f"Error searching for tools in plugin paths: {e}")
        
        # If we get here, we could not find a valid tools directory
        logger.error("No valid tools directory found with Python files")
        self.tools_dir = None  # Set to None to indicate no valid directory found
        
    async def connect(self, force=False):
        """Connect to the local tools by loading them."""
        if self.connected and not force:
            return True
            
        # Check if we have a valid tools directory
        if not self.tools_dir or not self.tools_dir.exists():
            logger.error("No valid tools directory found. Cannot load tools.")
            self.tools_metadata = {}  # Empty dictionary
            self.tool_instances = {}  # Empty dictionary
            self.connected = False
            return False
            
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
        for tool_file in tool_files:
            logger.debug(f"  Tool file: {tool_file.name}")
        
        # Load each tool file
        for path in tool_files:
            tool = self._load_tool_from_path(path)
            if tool:
                tools.append(tool)
                logger.info(f"Successfully loaded tool: {tool.name}")

        logger.info(f"Successfully loaded {len(tools)} local tools")
        
        # Log details of loaded tools
        for tool in tools:
            logger.info(f"Loaded tool: {tool.name} (Emoji: {tool.emoji})")
            
        return tools
    
    def _load_tool_from_path(self, path: pathlib.Path) -> Optional[Tool]:
        """
        Load a single tool from a Python file path.
        
        Args:
            path: Path to the Python file
            
        Returns:
            Tool object if successfully loaded, None otherwise
        """
        if path.name.startswith("_"):
            return None
            
        try:
            logger.debug(f"Attempting to load tool from: {path}")
            module_name = path.stem
            
            # Use importlib.util to load the module directly from file
            # This is more reliable than normal imports in packaged environments
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            
            if not spec:
                logger.warning(f"Could not create spec for {path}")
                return None
                
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod  
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