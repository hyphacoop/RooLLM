import sys
import pathlib
import tempfile
import os

def resolve_run_mcp_path() -> str:
    here = pathlib.Path(__file__).parent
    dev_path = here / "run_mcp_stdio.py"

    if dev_path.exists():
        # running locally
        return str(dev_path.resolve())

    # running from zipped plugin
    try:
        from importlib.resources import files
        code = files("hyphadevbot.roollm").joinpath("run_mcp_stdio.py").read_text()
    except Exception as e:
        raise RuntimeError("Couldn't load run_mcp_stdio.py from package") from e

    tmp = tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False)
    tmp.write(code)
    tmp.flush()
    tmp.close()
    return tmp.name

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "command": sys.executable,
            "args": [resolve_run_mcp_path()],
            "env": {
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        }
    }
}
