import os
import sys
import pathlib
import tempfile
import zipfile
import importlib.util

def extract_self_if_zipped():
    if not hasattr(sys, "_MEIPASS"):  # not pyinstaller
        spec = importlib.util.find_spec(__name__.split(".")[0])
        if spec and spec.origin and spec.origin.endswith(".mbp"):
            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(spec.origin, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            return pathlib.Path(temp_dir)
    return None

here = pathlib.Path(__file__).parent
path = here / "run_mcp_stdio.py"

extracted_dir = extract_self_if_zipped()
if extracted_dir:
    path = extracted_dir / "hyphadevbot" / "roollm" / "run_mcp_stdio.py"

MCP_CONFIG = {
    "mcp_adapters": {
        "minima": {
            "command": sys.executable,
            "args": [str(path.resolve())],
            "env": {
                "PYTHONPATH": str(extracted_dir) if extracted_dir else os.environ.get("PYTHONPATH", ""),
                "MCP_ADAPTER": "minima_adapter.MinimaRestAdapter"
            }
        }
    }
}
