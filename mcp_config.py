import os
import sys
import pathlib
import tempfile
import zipfile
import importlib.util

def extract_to_temp_if_zipped() -> pathlib.Path:
    # running inside .mbp? (Maubot plugin zip)
    spec = importlib.util.find_spec(__name__.split(".")[0])
    if spec and spec.origin and spec.origin.endswith(".mbp"):
        with zipfile.ZipFile(spec.origin, "r") as zipf:
            extracted_dir = pathlib.Path(tempfile.mkdtemp())
            zipf.extract("hyphadevbot/roollm/run_mcp_stdio.py", extracted_dir)
            return extracted_dir / "hyphadevbot" / "roollm" / "run_mcp_stdio.py"
    return None

here = pathlib.Path(__file__).parent
dev_script = here / "run_mcp_stdio.py"
script_path = dev_script if dev_script.exists() else extract_to_temp_if_zipped()

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
