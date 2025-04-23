import sys
import pathlib

here = pathlib.Path(__file__).parent

# are we running this locally from roollm/ or as part of hyphadevbot. zipped or installed?
in_dev_mode = (here / "run_mcp_stdio.py").exists()

if in_dev_mode:
    command = sys.executable
    args = [str((here / "run_mcp_stdio.py").resolve())]
else:
    command = sys.executable
    args = ["-m", "hyphadevbot.roollm.run_mcp_stdio"]

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "command": command,
            "args": args,
            "env": {
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        }
    }
}
