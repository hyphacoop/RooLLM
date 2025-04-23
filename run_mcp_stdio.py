# run_mcp_stdio.py
import sys
import json
import asyncio
import importlib
import os

def load_adapter(adapter_path):
    mod_name, class_name = adapter_path.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, class_name)()

async def main():
    adapter_path = os.getenv("MCP_ADAPTER", "minima_adapter.MinimaRestAdapter")
    sys.stderr.write(f"📦 Loading adapter: {adapter_path}\n")
    sys.stderr.flush()
    adapter = load_adapter(adapter_path)
    sys.stderr.write(f"✅ Adapter loaded: {adapter.__class__}\n")
    sys.stderr.flush()

    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        try:
            req = json.loads(line)
            method = req.get("method")
            req_id = req.get("id")

            if method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": name,
                            "description": meta.get("description", ""),
                            "inputSchema": meta.get("parameters", {})
                        }
                        for name, meta in adapter.tools.items()
                    ]
                }
            elif method == "tools/call":
                params = req["params"]
                name = params["tool"] if "tool" in params else params["name"]
                args = params["arguments"]
                result = await adapter.call_tool(name, args)
            else:
                raise Exception("Unknown method")

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }

        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": req.get("id", None),
                "error": {"code": -32000, "message": str(e)}
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
