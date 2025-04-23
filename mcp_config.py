import sys
import pathlib

here = pathlib.Path(__file__).parent

# if the script exists on disk, we're probably in local dev (REPL or unzipped plugin dir)
dev_mode = (here / "run_mcp_stdio.py").exists()

if dev_mode:
    command = sys.executable
    args = [str((here / "run_mcp_stdio.py").resolve())]
else:
    # fallback: extract the script to /tmp and run it directly
    import pkgutil
    import tempfile

    tmp_path = tempfile.NamedTemporaryFile(
        mode="w+", suffix=".py", delete=False
    )
    code = pkgutil.get_data(__package__, "run_mcp_stdio.py")
    tmp_path.write(code.decode("utf-8"))
    tmp_path.flush()
    tmp_path.close()

    command = sys.executable
    args = [tmp_path.name]

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
