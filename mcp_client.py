import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional

try:
    from .tools.tool_registry import Tool
except ImportError:
    from tools.tool_registry import Tool


class MCPClient:
    def __init__(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.proc = None
        self.stdin = None
        self.stdout = None

    async def connect(self):
        """Connect to the MCP server by spawning it as a subprocess."""
        self.proc = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.env},
        )
        self.stdin = self.proc.stdin
        self.stdout = self.proc.stdout


    async def _rpc(self, method: str, params: Dict[str, Any]) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        msg_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params
        }

        msg_json = json.dumps(request)
        self.stdin.write((msg_json + "\n").encode())
        await self.stdin.drain()

        while True:
            line = await self.stdout.readline()

            if not line:
                # Maybe the process crashed
                returncode = await self.proc.wait()
                stderr_output = await self.proc.stderr.read()
                raise Exception(f"[MCPClient] No response received. Process exited with code {returncode}.\nStderr: {stderr_output.decode()}")

            try:
                response = json.loads(line.decode())
                if response.get("id") == msg_id:
                    if "result" in response:
                        return response["result"]
                    elif "error" in response:
                        raise Exception(f"MCPClient error: {response['error']}")
            except json.JSONDecodeError as e:
                continue

    async def list_tools(self) -> List[Tool]:
        """Get the list of available tools from the MCP server."""
        result = await self._rpc("tools/list", {})
        return [
            Tool(
                name=tool_def["name"],
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("inputSchema", {}),
                adapter_name=self.name
            )
            for tool_def in result.get("tools", [])
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool with the given arguments."""
        return await self._rpc("tools/call", {
            "tool": tool_name,
            "arguments": arguments
        })

    async def close(self):
        """Close the connection to the MCP server."""
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()
            self.proc = None
            self.stdin = None
            self.stdout = None
