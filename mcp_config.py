import os

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": ".minima_adapter.MinimaRestAdapter"
            }
        },
        "local": {
            "mode": "inline",
            "env": {
                "MCP_ADAPTER": ".tools.local_tools_adapter.LocalToolsAdapter"
            }
        },
        "trello": {
            "mode": "subprocess",
            "command": "npx",
            "args": ["@delorenj/mcp-server-trello"],
            "env": {
                "TRELLO_API_KEY": os.getenv("TRELLO_API_KEY", ""),
                "TRELLO_TOKEN": os.getenv("TRELLO_TOKEN", ""),
                "TRELLO_BOARD_ID": os.getenv("TRELLO_BOARD_ID", "")
            }
        }
    }
}
