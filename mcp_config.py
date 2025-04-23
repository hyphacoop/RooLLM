import sys
import pathlib
import zipimport

# get the current file's location
here = pathlib.Path(__file__).parent
path = here / "run_mcp_stdio.py"

# check if we're in a zip (maubot plugin context)
running_in_zip = isinstance(__loader__, zipimport.zipimporter)

if running_in_zip:
    # use fully-qualified import path relative to plugin root
    args = ["-m", "hyphadevbot.roollm.run_mcp_stdio"]
else:
    # when running from source (e.g. python repl.py), just pass the path
    args = [str(path.resolve())]

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "command": sys.executable,
            "args": args,
            "env": {
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        }
    }
}
