from typing import Dict, List
import json
import importlib
import logging

try:
    from .llm_client import LLMClient
    from .tools.tool_registry import ToolRegistry, Tool
    from .mcp_client import MCPClient
except ImportError:
    from llm_client import LLMClient
    from tools.tool_registry import ToolRegistry, Tool
    from mcp_client import MCPClient

# Configure logging
logger = logging.getLogger(__name__)

def load_adapter_from_config(name: str, conf: dict, full_config: dict):
    """Load an adapter based on configuration."""
    mode = conf.get("mode", "inline")

    if mode == "subprocess":
        return MCPClient(
            name=name,
            command=conf["command"],
            args=conf["args"],
            env=conf.get("env", {})
        )

    adapter_path = conf["env"]["MCP_ADAPTER"]
    mod_name, class_name = adapter_path.rsplit(".", 1)
    
    try:
        # First try relative import
        if mod_name.startswith('.'):
            mod_name = mod_name.lstrip('.')
            try:
                mod = importlib.import_module(f".{mod_name}", package="roollm")
            except ImportError:
                # If that fails, try direct import
                mod = importlib.import_module(mod_name)
        else:
            mod = importlib.import_module(mod_name)
            
        adapter_cls = getattr(mod, class_name)
        return adapter_cls(config=full_config)
    except Exception as e:
        logger.error(f"Failed to load adapter {name} from {adapter_path}: {e}", exc_info=True)
        raise


class MCPLLMBridge:
    def __init__(self, config: Dict, llm_client: LLMClient, tool_registry=None, roollm=None):
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry or ToolRegistry()
        self.roollm = roollm
        self.mcp_clients: Dict[str, object] = {}
        self.initialized = False

    async def initialize(self):
        """Initialize the bridge by loading MCP adapter tools."""
        if self.initialized:
            logger.debug("Bridge already initialized, skipping initialization")
            return
            
        try:
            # Load MCP adapter tools
            logger.debug("Loading MCP adapter tools...")
            mcp_configs = self.config.get("mcp_adapters", {})
            
            for name, adapter_conf in mcp_configs.items():
                try:
                    # Create and configure the adapter
                    adapter = load_adapter_from_config(name, adapter_conf, self.config)
                    
                    # Set roo instance on local tools adapter
                    if hasattr(adapter, "roo"):
                        adapter.roo = self.roollm
                        
                    # Connect to the adapter
                    await adapter.connect()
                    
            # Get and register tools
                    tools = await adapter.list_tools()
                    for tool_item in tools:
                        # Handle both Tool objects (from MCPClient) and dict objects (from inline adapters)
                        if isinstance(tool_item, Tool):
                            tool_obj = tool_item
                            # Ensure adapter_name is set
                            if not tool_obj.adapter_name:
                                tool_obj.adapter_name = name
                        else:
                            # Wrap tool dict into Tool object expected by the registry
                            tool_obj = Tool.from_dict(tool_item, adapter_name=name)
                        self.tool_registry.register_tool(tool_obj)
                    
                    # For subprocess-based adapters (MCPClient), close the connection after
                    # getting tools. This prevents "event loop is closed" warnings when the
                    # init loop ends. The client will reconnect lazily when tools are called.
                    if hasattr(adapter, 'close') and hasattr(adapter, '_connected_loop'):
                        await adapter.close()
                        
                    # Store the adapter for later use
                    self.mcp_clients[name] = adapter
                    logger.debug(f"Loaded {len(tools)} tools from adapter {name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load adapter {name}: {e}", exc_info=True)
                    continue

            # Log final tool count
            all_tools = self.tool_registry.all_tools()
            logger.debug(f"Successfully loaded {len(all_tools)} total tools:")
            for tool in all_tools:
                logger.debug(f"- {tool.name} ({tool.adapter_name})")
                
            self.initialized = True

        except Exception as e:
            logger.error(f"Error during bridge initialization: {e}", exc_info=True)
            raise

    async def process_message(self, user: str, content: str, history: List[Dict], react_callback=None):
        # Ensure bridge is initialized
        if not self.initialized:
            await self.initialize()
            
        messages = history + [{"role": "user", "content": f"{user}: {content}"}]
        tools = self.tool_registry.openai_descriptions()

        # ReAct Loop - Continue until no more tool calls or max iterations reached
        max_iterations = self.config.get("react_max_iterations", 10)  # Configurable max iterations
        enable_react = self.config.get("enable_react_loop", True)  # Option to disable ReAct loop
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"ReAct iteration {iteration}")
            
            # Get response from LLM
            raw_response = await self.llm_client.invoke(messages, tools=tools)
            message = raw_response.get("message", {})

            # If no tool calls, we're done - return the response
            if "tool_calls" not in message:
                logger.debug(f"ReAct loop completed after {iteration} iterations - no more tool calls")
                return message

            # Add LLM response to messages for context
            messages.append(message)

            # Process tool calls sequentially
            tool_outputs = []
            for call in message["tool_calls"]:
                func = call.get("function", {})
                name = func.get("name")
                args = func.get("arguments", {})
                tool_call_id = call.get("id", name)

                # Get the tool from registry
                tool = self.tool_registry.get_tool(name)
                if not tool:
                    logger.warning(f"Tool {name} not found in registry")
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": f"Tool {name} not found"})
                    })
                    continue

                # Indicate tool usage if callback provided
                if react_callback:
                    await react_callback(tool.emoji or tool.name)

                try:
                    # Call through the appropriate adapter
                    adapter = self.mcp_clients.get(tool.adapter_name)
                    if not adapter:
                        raise ValueError(f"Adapter {tool.adapter_name} not found for tool {name}")
                        
                    logger.debug(f"Executing tool {name} with args: {args}")
                    result = await adapter.call_tool(name, args)
                    logger.debug(f"Tool {name} result: {result}")

                    # Add tool output to messages
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result)
                    })
                    
                except Exception as e:
                    logger.error(f"Error calling tool {name}: {e}", exc_info=True)
                    # Add error output
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": f"Tool execution failed: {str(e)}"})
                    })

            # Add tool outputs to messages
            messages.extend(tool_outputs)
            
            # If ReAct is disabled, get final response and break
            if not enable_react:
                logger.debug("ReAct loop disabled - getting final response after tool execution")
                final_response = await self.llm_client.invoke(messages, tools=[])
                return final_response.get("message", {})
            
            # Continue loop to allow LLM to reason about results and potentially call more tools
            
        # If we've reached max iterations, get a final response
        logger.warning(f"ReAct loop reached max iterations ({max_iterations}), getting final response")
        final_response = await self.llm_client.invoke(messages, tools=[])  # No tools to prevent more calls
        return final_response.get("message", {})