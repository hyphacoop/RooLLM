import logging
from typing import Dict, Any, List
import importlib.util
import os
import sys

# Add the parent directory to sys.path to allow relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

logger = logging.getLogger(__name__)

# mport the modules
try: 
    from .tool_registry import Tool
    from .load_local_tools import load_local_tools
except ImportError as e:
    try:
        from tool_registry import Tool
        from load_local_tools import load_local_tools
    except ImportError as e:
        logger.error(f"Failed to import modules: {e}")
        raise


class LocalToolsAdapter:
    """
    Adapter that wraps local tools in the MCP interface.
    This allows local tools to be loaded and used through the MCP bridge.
    """
    
    def __init__(self, config=None):
        """
        Initialize the local tools adapter.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.connected = False
        self.tools = {}
        self.roo = None  # Will be set by the bridge
        
    async def connect(self, force=False):
        """Connect to the local tools by loading them."""
        if self.connected and not force:
            return True
            
        try:
            # Load local tools
            local_tools = load_local_tools(config=self.config)
            
            # Convert tools to MCP format
            self.tools = {
                tool.name: {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "emoji": tool.emoji
                }
                for tool in local_tools
            }
            
            self.connected = True
            logger.info(f"Successfully loaded {len(self.tools)} local tools")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load local tools: {e}")
            self.connected = False
            return False
            
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get the list of available local tools."""
        if not self.connected:
            await self.connect()
            
        return list(self.tools.values())
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific local tool with the given arguments."""
        if not self.connected:
            await self.connect()
            
        # Reload tools to get fresh instances
        local_tools = load_local_tools(config=self.config)
        tool = next((t for t in local_tools if t.name == tool_name), None)
        
        if not tool or not tool.run_fn:
            raise ValueError(f"Tool {tool_name} not found or has no run function")
            
        # Call the tool's run function with the roo instance
        return await tool.run_fn(self.roo, arguments, "mcp") 