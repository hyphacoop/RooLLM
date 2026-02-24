import aiohttp
import json
import inspect
import logging
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str, model: str, username: str = "", password: str = "", stream: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.auth = aiohttp.BasicAuth(username, password) if username and password else None
        self.stream = stream

    def _build_payload(
        self,
        messages: list,
        tools: Optional[list] = None,
        extra_options: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": self.stream if stream is None else stream,
        }

        if tools:
            payload["tools"] = tools

        if extra_options:
            payload.update(extra_options)

        return payload

    @staticmethod
    def _parse_json_or_ndjson(body: str) -> dict:
        body = body.strip()
        if not body:
            raise Exception("LLMClient Error: Empty response body")

        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback for NDJSON bodies (e.g., if stream=true is enabled upstream)
        last_obj = None
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    last_obj = obj
            except json.JSONDecodeError:
                continue

        if last_obj is not None:
            return last_obj

        raise Exception("LLMClient Error: Could not parse JSON response")

    async def invoke(
        self,
        messages: list,
        tools: Optional[list] = None,
        extra_options: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> dict:
        payload = self._build_payload(messages, tools=tools, extra_options=extra_options, stream=stream)
        url = f"{self.base_url}/api/chat"

        async with aiohttp.ClientSession(auth=self.auth) as session:
            async with session.post(url, json=payload) as response:
                body = await response.text()
                if response.status == 200:
                    return self._parse_json_or_ndjson(body)
                raise Exception(f"LLMClient Error: {response.status} - {body}")

    async def invoke_stream(
        self,
        messages: list,
        tools: Optional[list] = None,
        extra_options: Optional[dict] = None,
        on_delta: Optional[Callable[[str], Any]] = None,
    ) -> Dict[str, Any]:
        payload = self._build_payload(messages, tools=tools, extra_options=extra_options, stream=True)
        url = f"{self.base_url}/api/chat"

        async with aiohttp.ClientSession(auth=self.auth) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"LLMClient Error: {response.status} - {body}")

                buffer = ""
                final_obj: Optional[Dict[str, Any]] = None
                streamed_content: list[str] = []
                streamed_role: Optional[str] = None
                streamed_tool_calls: Optional[list] = None

                async def handle_line(line: str):
                    nonlocal final_obj, streamed_role, streamed_tool_calls

                    line = line.strip()
                    if not line:
                        return

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Skipping non-JSON stream line from LLM")
                        return

                    if not isinstance(obj, dict):
                        return

                    final_obj = obj
                    message = obj.get("message", {})
                    if not isinstance(message, dict):
                        return

                    role = message.get("role")
                    if isinstance(role, str):
                        streamed_role = role

                    if "tool_calls" in message and isinstance(message["tool_calls"], list):
                        streamed_tool_calls = message["tool_calls"]

                    delta = message.get("content")
                    if isinstance(delta, str) and delta:
                        streamed_content.append(delta)
                        if on_delta:
                            result = on_delta(delta)
                            if inspect.isawaitable(result):
                                await result

                async for chunk in response.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        await handle_line(line)

                if buffer.strip():
                    await handle_line(buffer)

                if final_obj is None:
                    raise Exception("LLMClient Error: Empty streaming response")

                final_message = final_obj.get("message", {})
                if not isinstance(final_message, dict):
                    final_message = {}

                # Reconstruct content from deltas (works for NDJSON streaming payloads).
                if streamed_content:
                    final_message["content"] = "".join(streamed_content)
                elif "content" not in final_message:
                    final_message["content"] = ""

                if "role" not in final_message:
                    final_message["role"] = streamed_role or "assistant"

                if "tool_calls" not in final_message and streamed_tool_calls is not None:
                    final_message["tool_calls"] = streamed_tool_calls

                final_obj["message"] = final_message
                return final_obj
