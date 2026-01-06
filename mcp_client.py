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
        self._connected_loop = None  # Track which loop we connected in
        self._cached_tools = None  # Cache tools list to avoid re-fetching after reconnect

    async def connect(self):
        """Connect to the MCP server by spawning it as a subprocess."""
        # Kill any existing process (without awaiting - it may be on a different loop)
        if self.proc:
            try:
                self.proc.kill()
            except (ProcessLookupError, OSError):
                pass  # Process already gone
            self.proc = None
            self.stdin = None
            self.stdout = None
            
        self.proc = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.env},
        )
        self.stdin = self.proc.stdin
        self.stdout = self.proc.stdout
        self._connected_loop = asyncio.get_running_loop()

    async def _ensure_connection(self):
        """Ensure we're connected to the correct event loop."""
        current_loop = asyncio.get_running_loop()
        if self._connected_loop is not current_loop or self.proc is None:
            # Reconnect in the current loop
            await self.connect()

    async def _rpc(self, method: str, params: Dict[str, Any]) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        # Ensure we're connected in the current event loop
        await self._ensure_connection()
        
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
        tools = [
            Tool(
                name=tool_def["name"],
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("inputSchema", {}),
                adapter_name=self.name
            )
            for tool_def in result.get("tools", [])
        ]
        self._cached_tools = tools
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool with the given arguments."""
        return await self._rpc("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    async def close(self):
        """Close the connection to the MCP server."""
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except ProcessLookupError:
                pass  # Process already gone
            self.proc = None
            self.stdin = None
            self.stdout = None
            self._connected_loop = None
