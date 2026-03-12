import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_client import LLMClient


class FakeContent:
    def __init__(self, chunks):
        self._chunks = [chunk.encode("utf-8") for chunk in chunks]

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class FakeResponse:
    def __init__(self, chunks, status=200):
        self.status = status
        self.content = FakeContent(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return "".join(chunk.decode("utf-8") for chunk in self.content._chunks)


class FakeSession:
    def __init__(self, chunks, capture_payload):
        self._chunks = chunks
        self._capture_payload = capture_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        self._capture_payload.append({"url": url, "json": json})
        return FakeResponse(self._chunks)


class LLMClientStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_closes_think_block_before_tool_turn_handoff(self):
        chunks = [
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "thinking": "Plan the tool call.",
                    }
                }
            )
            + "\n",
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {"name": "query", "arguments": {}},
                            }
                        ],
                    }
                }
            )
            + "\n",
        ]
        seen = []
        payloads = []

        async def on_delta(delta):
            seen.append(delta)

        client = LLMClient("http://example.test", "fake-model")

        with patch("llm_client.aiohttp.ClientSession", return_value=FakeSession(chunks, payloads)):
            result = await client.invoke_stream(
                [{"role": "user", "content": "How much money do Hypha members make?"}],
                tools=[{"type": "function", "function": {"name": "query"}}],
                on_delta=on_delta,
            )

        self.assertEqual(seen, ["<think>", "Plan the tool call.", "</think>"])
        self.assertEqual(result["message"]["content"], "<think>Plan the tool call.</think>")
        self.assertEqual(result["message"]["tool_calls"][0]["function"]["name"], "query")
        self.assertTrue(payloads)
        self.assertEqual(payloads[0]["json"]["stream"], True)

    async def test_closes_open_think_block_at_end_of_stream(self):
        chunks = [
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "thinking": "Reason without emitting content.",
                    }
                }
            )
            + "\n"
        ]
        seen = []

        async def on_delta(delta):
            seen.append(delta)

        client = LLMClient("http://example.test", "fake-model")

        with patch("llm_client.aiohttp.ClientSession", return_value=FakeSession(chunks, [])):
            result = await client.invoke_stream(
                [{"role": "user", "content": "Reply later"}],
                on_delta=on_delta,
            )

        self.assertEqual(seen, ["<think>", "Reason without emitting content.", "</think>"])
        self.assertEqual(
            result["message"]["content"],
            "<think>Reason without emitting content.</think>",
        )


if __name__ == "__main__":
    unittest.main()
