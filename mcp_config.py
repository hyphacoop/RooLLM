import pathlib
import sys

script_path = pathlib.Path(__file__).parent / "run_mcp_stdio.py"

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "command": sys.executable,  
            "args": [str(script_path.resolve())],
            "env": {
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        }
    }
}
