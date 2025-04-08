from dotenv import load_dotenv; load_dotenv()
from mcp.server.fastmcp import FastMCP
from datetime import datetime
import asyncio
from roollm import RooLLM, make_ollama_inference
import ast
import json
import os
import sys
import traceback
import inspect
import time

# 🧠 Create the MCP server
mcp = FastMCP("RooLLM MCP Server")

# 🔐 Load environment
print("🔐 Loaded LLM URL:", os.getenv("ROO_LLM_URL", "Not set"), file=sys.stderr)
print("🔐 Loaded LLM Username:", os.getenv("ROO_LLM_AUTH_USERNAME", "Not set"), file=sys.stderr)

# Create a config with all the necessary tokens
config = {
    "gh_token": os.getenv("GITHUB_TOKEN", ""),
    "google_creds": os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
}

# 🔌 Set up Ollama inference with env vars
inference = make_ollama_inference()

# Initialize RooLLM with ALL tools, regardless of config
from roollm import BASE_TOOL_LIST, GITHUB_TOOL_LIST, GOOGLE_TOOL_LIST, DEFAULT_TOOL_LIST
ALL_TOOLS = BASE_TOOL_LIST + GITHUB_TOOL_LIST + GOOGLE_TOOL_LIST

# Print the tools we're attempting to load
print(f"🧰 Attempting to load tools: {ALL_TOOLS}", file=sys.stderr)

# Create RooLLM instance with all tools and the config
roo = RooLLM(inference, tool_list=ALL_TOOLS, config=config)
print(f"🔧 Loaded tools: {list(roo.tools.tools.keys())}", file=sys.stderr)

# Track registered tools for logging
registered_tools = {}

# Tool timeouts in seconds
TOOL_TIMEOUTS = {
    "search_handbook": 45,  # Handbook search may take longer
    "calc": 5,
    "get_upcoming_holiday": 15,
    "get_archive_categories": 15,
    "github_issues_operations": 30,
    "github_pull_requests_operations": 30,
    "get_upcoming_vacations": 30,
    "fetch_remaining_vacation_days": 30
}
DEFAULT_TIMEOUT = 25  # Default timeout for tools not specifically listed

# Dispatcher tools that act like routers for GitHub ops
DISPATCHER_TOOLS = {
    "github_issues_operations",
    "github_pull_requests_operations"
}

def get_parameter_mapping(tool_name, tool_module):
    """Extract the main parameter name from a tool module's parameters."""
    if not hasattr(tool_module, "parameters"):
        return None
    
    params = tool_module.parameters.get("properties", {})
    required = tool_module.parameters.get("required", [])
    
    # If there's only one required parameter, use that
    if len(required) == 1:
        return required[0]
    
    # Otherwise, try to find a parameter that looks like the main one
    common_main_params = ["query", "expression", "input", "text", "content", "action"]
    for param in common_main_params:
        if param in params:
            return param
    
    # Fall back to the first parameter if we can't determine
    if params:
        return next(iter(params))
    
    return None

async def with_timeout(coroutine, timeout_seconds):
    """Execute coroutine with timeout and better error handling."""
    try:
        return await asyncio.wait_for(coroutine, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"⏰ Operation timed out after {timeout_seconds} seconds", file=sys.stderr)
        return {"error": f"Operation timed out after {timeout_seconds} seconds"}
    except Exception as e:
        print(f"❌ Error during operation: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"error": f"Error during operation: {str(e)}"}

def register_tool(tool_name, tool_module):
    """Register a tool with the MCP server based on its module definition."""
    print(f"📝 Registering tool: {tool_name}", file=sys.stderr)
    
    # Determine if this is a dispatcher tool
    is_dispatcher = tool_name in DISPATCHER_TOOLS
    
    # Get parameter definitions if available
    param_defs = {}
    if hasattr(tool_module, "parameters"):
        param_defs = tool_module.parameters.get("properties", {})
    
    # Determine the main parameter name for this tool
    main_param = get_parameter_mapping(tool_name, tool_module)
    print(f"🔑 Main parameter for {tool_name}: {main_param}", file=sys.stderr)
    
    # Get timeout for this tool
    tool_timeout = TOOL_TIMEOUTS.get(tool_name, DEFAULT_TIMEOUT)
    
    @mcp.tool(name=tool_name)
    async def tool_proxy(**kwargs):
        start_time = time.time()
        request_id = hash(str(start_time) + tool_name)
        print(f"🛠️ [{request_id}] Tool {tool_name} called with kwargs: {kwargs}", file=sys.stderr)
        
        # Process kwargs if it's a string - direct mapping to main parameter
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str):
            value = kwargs["kwargs"].strip('"').strip("'")
            
            if main_param:
                # Use the identified main parameter
                processed_kwargs = {main_param: value}
                print(f"📦 [{request_id}] Mapped kwargs to {main_param}: {processed_kwargs}", file=sys.stderr)
            else:
                # If we couldn't determine a main parameter, try parsing as JSON/dict
                try:
                    processed_kwargs = json.loads(value)
                except:
                    try:
                        processed_kwargs = ast.literal_eval(value)
                    except:
                        # Keep as is
                        processed_kwargs = {"kwargs": value}
        else:
            # Use kwargs as is
            processed_kwargs = kwargs
        
        try:
            # Call the tool with processed kwargs
            print(f"🔍 [{request_id}] Calling {tool_name} with timeout {tool_timeout}s: {processed_kwargs}", file=sys.stderr)
            
            # Always call the tool() method directly on the module with timeout
            if hasattr(tool_module, "tool"):
                tool_coroutine = tool_module.tool(roo, processed_kwargs, "mcp")
                result = await with_timeout(tool_coroutine, tool_timeout)
            else:
                raise AttributeError(f"Module {tool_name} does not have a 'tool' method")
            
            execution_time = time.time() - start_time
            print(f"✅ [{request_id}] Result from {tool_name} (took {execution_time:.2f}s): {result}", file=sys.stderr)
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Error in tool {tool_name} after {execution_time:.2f}s: {e}"
            print(f"❌ [{request_id}] {error_msg}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return {"error": error_msg}
    
    # Set up function annotations from param_defs
    annotations = {}
    for k, v in param_defs.items():
        if v.get("type") == "string":
            annotations[k] = str
        elif v.get("type") == "integer":
            annotations[k] = int
        else:
            annotations[k] = str
    
    tool_proxy.__annotations__ = annotations
    
    # Set up function docstring from tool description
    description = getattr(tool_module, "description", f"Tool for {tool_name}")
    params_doc = "\n".join(f"- `{k}`: {v.get('description', '')}" for k, v in param_defs.items())
    tool_proxy.__doc__ = f"{description}\n\nParameters:\n{params_doc}"
    
    return tool_proxy

# 🔁 Register all tools dynamically
for tool_name, tool_module in roo.tools.tools.items():
    tool_func = register_tool(tool_name, tool_module)
    globals()[tool_name] = tool_func
    registered_tools[tool_name] = {
        "main_param": get_parameter_mapping(tool_name, tool_module),
        "is_dispatcher": tool_name in DISPATCHER_TOOLS,
        "description": getattr(tool_module, "description", ""),
        "emoji": getattr(tool_module, "emoji", "🔧"),
        "timeout": TOOL_TIMEOUTS.get(tool_name, DEFAULT_TIMEOUT)
    }

# 🕒 Resources
@mcp.resource("clock://now")
def get_current_time() -> str:
    return datetime.now().isoformat()

@mcp.resource("config://tool-list")
def list_all_tools() -> list[str]:
    return list(roo.tools.tools.keys())

@mcp.resource("tools://{tool_name}/help")
def get_tool_documentation(tool_name: str) -> str:
    """Get detailed documentation for a specific tool"""
    if tool_name in registered_tools:
        return f"# {tool_name} {registered_tools[tool_name]['emoji']}\n\n{registered_tools[tool_name]['description']}"
    return f"Tool {tool_name} not found"

# 💬 Prompt
@mcp.prompt()
def explain_issue(issue_description: str) -> str:
    return f"What are the potential causes and fixes for this GitHub issue?\n\n{issue_description}"

# 🚀 Run
if __name__ == "__main__":
    print("🚀 Starting MCP server...", file=sys.stderr)
    print(f"📋 Registered tools: {json.dumps(registered_tools, indent=2)}", file=sys.stderr)
    
    # Try to set timeout if supported
    try:
        mcp.timeout = 60  # Increased global timeout
        print(f"⏱️ Set FastMCP timeout to {mcp.timeout} seconds", file=sys.stderr)
    except:
        print("⚠️ Could not set FastMCP timeout - using coroutine timeouts only", file=sys.stderr)
    
    try:
        mcp.run()
    except Exception as e:
        print(f"💥 Server crashed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

# 🧩 Required for dev mode
server = mcp