import logging
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional

from .tool_registry import Tool

logger = logging.getLogger(__name__)

class LocalToolsAdapter:
    """Simple adapter for loading and managing local tools."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.tools: Dict[str, Tool] = {}
        self.roo = None
        
    async def connect(self, force=False):
        """Load all local tools."""
        if self.tools and not force:
            return True
            
        try:
            tools_dir = Path(__file__).parent
            for file in tools_dir.glob("*.py"):
                if file.stem.startswith('_') or file.stem in ['local_tools_adapter', 'tool_registry', 'tools_class']:
                    continue
                    
                try:
                    module = importlib.import_module(f".{file.stem}", package=__package__)
                    if not hasattr(module, "tool"):
                        continue
                        
                    tool = Tool(
                        name=getattr(module, "name", file.stem),
                        description=getattr(module, "description", "No description."),
                        input_schema=getattr(module, "parameters", {"type": "object", "properties": {}}),
                        adapter_name="local",
                        run_fn=module.tool,
                        emoji=getattr(module, "emoji", None)
                    )
                    self.tools[tool.name] = tool
                    
                except Exception as e:
                    logger.error(f"Failed to load tool {file.stem}: {e}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            return False
            
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools in OpenAI format."""
        if not self.tools:
            await self.connect()
            
        return [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "emoji": tool.emoji
        } for tool in self.tools.values()]
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments."""
        if not self.tools:
            await self.connect()
            
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")
            
        try:
            return await tool.run_fn(self.roo, arguments, "mcp")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}