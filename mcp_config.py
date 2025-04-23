import sys
import os
import tempfile
import zipfile
import pathlib
import importlib.util


def extract_roollm_dir() -> pathlib.Path:
    """
    Extracts the full hyphadevbot/roollm/ directory to a temp folder,
    whether from a zipped .mbp or local dev. Returns the path to run_mcp_stdio.py
    """
    module_root = __name__.split(".")[0]
    spec = importlib.util.find_spec(module_root)

    if spec and spec.origin and spec.origin.endswith(".mbp"):
        # running from a zipped plugin archive
        with zipfile.ZipFile(spec.origin, "r") as zipf:
            extracted_dir = pathlib.Path("/tmp/maubot_mcp/hyphadevbot")
            for zipinfo in zipf.infolist():
                if zipinfo.filename.startswith("hyphadevbot/roollm/"):
                    out_path = extracted_dir / zipinfo.filename
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    zipf.extract(zipinfo, extracted_dir)
                    print(f"✅ extracted: {out_path}")


            script_path = extracted_dir / "hyphadevbot" / "roollm" / "run_mcp_stdio.py"
            if not script_path.exists():
                raise RuntimeError(f"🚨 run_mcp_stdio.py not found at: {script_path}")

            sys.path.insert(0, str(extracted_dir))  # allow imports like minima_adapter
            return script_path

    else:
        # fallback to local dev mode
        here = pathlib.Path(__file__).parent
        roollm_dir = here
        extracted_dir = pathlib.Path(tempfile.mkdtemp())
        extracted_roollm = extracted_dir / "hyphadevbot" / "roollm"
        extracted_roollm.mkdir(parents=True, exist_ok=True)

        for file in roollm_dir.glob("*.py"):
            (extracted_roollm / file.name).write_text(file.read_text())

        sys.path.insert(0, str(extracted_dir))
        return extracted_roollm / "run_mcp_stdio.py"


script_path = extract_roollm_dir()

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
