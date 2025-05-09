import logging
import importlib

from typing import Dict, Any, List, Optional

if hasattr(importlib, 'resources'):
    import importlib.resources as importlib_resources
else: # Older Python versions might need the backport
    import importlib_resources 

from .tool_registry import Tool

logger = logging.getLogger(__name__)

class LocalToolsAdapter:
    """Simple adapter for loading and managing local tools."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.tools: Dict[str, Tool] = {}
        self.roo = None # This will be set via the bridge
        logger.debug("LocalToolsAdapter initialized.")
        
    async def connect(self, force=False):
        """Load all local tools."""
        logger.debug(f"LocalToolsAdapter.connect called. force={force}, current tools count: {len(self.tools)}")
        if self.tools and not force:
            logger.debug("Tools already loaded and force is False. Skipping.")
            return True
        
        self.tools = {}
        logger.debug("Tools cache cleared for loading.")
            
        try:
            # Get a reference to the current package ('hyphadevbot.roollm.tools')
            # __name__ is 'hyphadevbot.roollm.tools.local_tools_adapter'
            # __package__ is 'hyphadevbot.roollm.tools'
            current_package_name = __package__ 
            logger.debug(f"Attempting to scan for tools in package: {current_package_name}")

            package_ref = importlib_resources.files(current_package_name)
            logger.debug(f"  Package reference obtained: {package_ref}")

            found_files_count = 0
            processed_files_count = 0

            # Iterate through items in the package directory
            for item_ref in package_ref.iterdir():
                if item_ref.is_file() and item_ref.name.endswith(".py"):
                    found_files_count += 1
                    file_name = item_ref.name
                    file_stem = file_name[:-3] # Remove .py

                    logger.debug(f"  Found potential tool file: {file_name}")
                    
                    if file_stem.startswith('_') or file_stem in ['local_tools_adapter', 'tool_registry', 'tools_class']:
                        logger.debug(f"    Skipping file: {file_name} (matches skip criteria)")
                        continue
                    
                    logger.debug(f"    Processing file: {file_name} (stem: {file_stem})")
                    processed_files_count += 1
                    
                    try:
                        logger.debug(f"      Attempting to import module '.{file_stem}' from package '{current_package_name}'")
                        module = importlib.import_module(f".{file_stem}", package=current_package_name)
                        logger.debug(f"      Successfully imported module: {module}")
                        
                        if not hasattr(module, "tool"):
                            logger.debug(f"      Module '{file_stem}' does NOT have a 'tool' attribute. Skipping tool registration.")
                            continue
                        
                        logger.debug(f"      Module '{file_stem}' HAS a 'tool' attribute. Proceeding to create Tool object.")
                
                        tool_name = getattr(module, "name", file_stem)
                        tool_description = getattr(module, "description", "No description provided.")
                        tool_parameters = getattr(module, "parameters", {"type": "object", "properties": {}}) # OpenAI schema
                        tool_emoji = getattr(module, "emoji", None)
                        
                        logger.debug(f"        Tool Name: {tool_name}")
                        logger.debug(f"        Tool Description: {tool_description}")
                        logger.debug(f"        Tool Emoji: {tool_emoji}")

                        tool_instance = Tool(
                            name=tool_name,
                            description=tool_description,
                            input_schema=tool_parameters,
                            adapter_name="local", # This adapter's name
                            run_fn=module.tool,
                            emoji=tool_emoji
                        )
                        self.tools[tool_instance.name] = tool_instance
                        logger.debug(f"      Successfully created and registered tool: {tool_instance.name}")
                        
                    except ImportError as ie:
                        logger.error(f"    IMPORT ERROR while loading tool '{file_stem}': {ie}", exc_info=True)
                    except AttributeError as ae:
                        logger.error(f"    ATTRIBUTE ERROR while processing tool '{file_stem}' (likely missing 'name', 'description', or 'parameters'): {ae}", exc_info=True)
                    except Exception as e:
                        logger.error(f"    UNEXPECTED ERROR while loading tool '{file_stem}': {e}", exc_info=True)
                else:
                    if not item_ref.name.endswith(".py"):
                         logger.debug(f"  Skipping non-.py item: {item_ref.name}")
                    elif not item_ref.is_file():
                         logger.debug(f"  Skipping non-file item: {item_ref.name}")


            logger.debug(f"Finished scanning. Found {found_files_count} .py files. Attempted to process {processed_files_count} files.")
            logger.debug(f"Total tools loaded by LocalToolsAdapter: {len(self.tools)}")
            if self.tools:
                logger.debug(f"Loaded tool names: {list(self.tools.keys())}")

            return True
            
        except Exception as e:
            logger.error(f"  FATAL ERROR during LocalToolsAdapter.connect (outside file loop): {e}", exc_info=True)
            return False
            
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools in OpenAI format."""
        logger.debug(f"LocalToolsAdapter.list_tools called. Current tools count: {len(self.tools)}")
        if not self.tools:
            # Potentially connect if tools haven't been loaded yet, though connect is usually called by bridge.initialize
            logger.debug("list_tools: No tools loaded, attempting to connect.")
            await self.connect(force=True) # Force connect if list_tools is called and tools are empty
            
        tool_list_for_openai = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema, # Make sure this is the correct attribute from your Tool class
            "emoji": tool.emoji
        } for tool in self.tools.values()]
        logger.debug(f"Returning {len(tool_list_for_openai)} tools for OpenAI description.")
        return tool_list_for_openai
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments."""
        logger.debug(f"LocalToolsAdapter.call_tool called for tool: {tool_name} with args: {arguments}")
        if not self.tools:
            logger.debug("call_tool: No tools loaded, attempting to connect (should ideally be pre-connected).")
            await self.connect(force=True)
            
        tool_to_call = self.tools.get(tool_name)
        if not tool_to_call:
            logger.error(f"Tool '{tool_name}' not found in LocalToolsAdapter.")
            raise ValueError(f"Tool {tool_name} not found")
            
        try:
            logger.debug(f"Executing tool '{tool_name}'. self.roo is set: {self.roo is not None}")
            # The tool function signature is async def tool(roo_instance, args, mcp_context=None):
            return await tool_to_call.run_fn(self.roo, arguments, "mcp_local_context") 
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}
