MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        },
        "local": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": "tools.local_tools_adapter.LocalToolsAdapter"
            }
        }
    }
}
