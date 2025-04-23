import sys
import json
import asyncio
import importlib
import os
import traceback


def load_adapter(adapter_path: str):
    mod_name, class_name = adapter_path.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, class_name)()


async def handle_request(adapter, req: dict):
    method = req.get("method")
    req_id = req.get("id")

    try:
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
            name = params.get("tool") or params.get("name")
            args = params.get("arguments", {})
            result = await adapter.call_tool(name, args)

        else:
            raise ValueError(f"Unknown method: {method}")

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32000,
                "message": str(e),
                "data": traceback.format_exc()
            }
        }


async def main():
    adapter_path = os.getenv("MCP_ADAPTER", "minima_adapter.MinimaRestAdapter")
    sys.stderr.write(f"📦 Loading adapter: {adapter_path}\n")
    sys.stderr.flush()

    adapter = load_adapter(adapter_path)
    sys.stderr.write(f"✅ Adapter loaded: {adapter.__class__.__name__}\n")
    sys.stderr.flush()

    loop = asyncio.get_event_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break  # EOF

        try:
            req = json.loads(line)
            response = await handle_request(adapter, req)
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Invalid request: {e}",
                    "data": traceback.format_exc()
                }
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
