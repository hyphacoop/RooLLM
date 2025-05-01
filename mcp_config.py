MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": "roollm.minima_adapter.MinimaRestAdapter"
            }
        },
        "local": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": "roollm.local_tools_adapter.LocalToolsAdapter"
            }
        }
    }
}
