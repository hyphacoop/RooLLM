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
                    for tool_dict in tools:
                        # Wrap tool dict into Tool object expected by the registry
                        tool_obj = Tool.from_dict(tool_dict, adapter_name=name)
                        self.tool_registry.register_tool(tool_obj)
                        
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

    async def _emit_stream_chunks(self, content: str, stream_callback, chunk_size: int = 32):
        """Emit existing text to a stream callback in small chunks."""
        if not content or not stream_callback:
            return

        for i in range(0, len(content), chunk_size):
            await stream_callback(content[i:i + chunk_size])

    async def process_message(
        self,
        user: str,
        content: str,
        history: List[Dict],
        react_callback=None,
        stream_callback=None,
    ):
        # Ensure bridge is initialized
        if not self.initialized:
            await self.initialize()
            
        messages = history + [{"role": "user", "content": f"{user}: {content}"}]
        tools = self.tool_registry.openai_descriptions()

        # ReAct Loop - Continue until no more tool calls or max iterations reached
        max_iterations = self.config.get("react_max_iterations", 10)  # Configurable max iterations
        enable_react = self.config.get("enable_react_loop", True)  # Option to disable ReAct loop
        max_same_tool_calls = int(self.config.get("max_same_tool_calls_per_turn", 5))
        max_query_tool_calls = int(self.config.get("max_query_tool_calls_per_turn", 2))
        iteration = 0
        had_tool_calls = False
        tool_call_counts = {}
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"ReAct iteration {iteration}")
            
            # Get response from LLM
            use_first_turn_stream = stream_callback is not None and iteration == 1
            if use_first_turn_stream:
                try:
                    raw_response = await self.llm_client.invoke_stream(
                        messages,
                        tools=tools,
                        on_delta=stream_callback,
                    )
                except Exception as e:
                    logger.warning(f"First-turn streaming failed, falling back to non-stream call: {e}")
                    raw_response = await self.llm_client.invoke(messages, tools=tools, stream=False)
            else:
                raw_response = await self.llm_client.invoke(messages, tools=tools, stream=False)
            message = raw_response.get("message", {})
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list):
                tool_calls = []

            # If no tool calls, we're done - return the response
            if not tool_calls:
                logger.debug(f"ReAct loop completed after {iteration} iterations - no more tool calls")

                # If we already executed tools, generate a dedicated final response and stream it.
                if stream_callback and had_tool_calls:
                    final_response = await self.llm_client.invoke_stream(
                        messages,
                        tools=[],
                        on_delta=stream_callback,
                    )
                    return final_response.get("message", {})

                # For direct (no-tool) answers:
                # - iteration 1 is already streamed above when possible
                # - fallback to chunked emit for non-stream models
                if stream_callback and not use_first_turn_stream:
                    await self._emit_stream_chunks(message.get("content", ""), stream_callback)
                return message

            had_tool_calls = True

            # Add LLM response to messages for context
            messages.append(message)

            # Process tool calls sequentially
            tool_outputs = []
            for call in tool_calls:
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

                # Guardrail against runaway repeated tool calls in a single user turn
                tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
                max_for_tool = max_query_tool_calls if name == "query" else max_same_tool_calls
                if tool_call_counts[name] > max_for_tool:
                    logger.warning(
                        f"Skipping repeated tool call: {name} "
                        f"(count={tool_call_counts[name]}, limit={max_for_tool})"
                    )
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({
                            "error": (
                                f"Tool call limit reached for '{name}' in this turn "
                                f"(limit={max_for_tool})."
                            )
                        })
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
                if stream_callback:
                    final_response = await self.llm_client.invoke_stream(
                        messages,
                        tools=[],
                        on_delta=stream_callback,
                    )
                else:
                    final_response = await self.llm_client.invoke(messages, tools=[], stream=False)
                return final_response.get("message", {})
            
            # Continue loop to allow LLM to reason about results and potentially call more tools
            
        # If we've reached max iterations, get a final response
        logger.warning(f"ReAct loop reached max iterations ({max_iterations}), getting final response")
        if stream_callback:
            final_response = await self.llm_client.invoke_stream(
                messages,
                tools=[],
                on_delta=stream_callback,
            )
        else:
            final_response = await self.llm_client.invoke(messages, tools=[], stream=False)  # No tools to prevent more calls
        return final_response.get("message", {})
