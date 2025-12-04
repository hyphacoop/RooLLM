MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": ".minima_adapter.MinimaRestAdapter"
            }
        }
    },
    "auto_rag_enabled": True,  # Automatically search knowledge base for every query
    "react_max_iterations": 10,  # Max ReAct loop iterations (LLM can make multiple tool calls)
    "enable_react_loop": True  # Enable ReAct loop for iterative reasoning and tool use
}
