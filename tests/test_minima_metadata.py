import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from minima_adapter import MinimaRestAdapter


def make_adapter(metadata_enabled: bool) -> MinimaRestAdapter:
    config = {
        "USE_MINIMA_MCP": True,
        "USE_MINIMA_METADATA": metadata_enabled,
        "MINIMA_MCP_SERVER_URL": "http://localhost:8001",
    }
    return MinimaRestAdapter(config=config)


class TestMetadataToolGating(unittest.TestCase):
    def test_metadata_tools_absent_when_disabled(self):
        adapter = make_adapter(metadata_enabled=False)
        self.assertNotIn("get_file_metadata", adapter.tools)
        self.assertNotIn("update_file_metadata", adapter.tools)
        self.assertNotIn("list_file_metadata", adapter.tools)

    def test_metadata_tools_present_when_enabled(self):
        adapter = make_adapter(metadata_enabled=True)
        self.assertIn("get_file_metadata", adapter.tools)
        self.assertIn("update_file_metadata", adapter.tools)
        self.assertIn("list_file_metadata", adapter.tools)

    def test_query_tool_always_present(self):
        self.assertIn("query", make_adapter(metadata_enabled=False).tools)
        self.assertIn("query", make_adapter(metadata_enabled=True).tools)

    def test_query_description_omits_metadata_when_disabled(self):
        desc = make_adapter(metadata_enabled=False).tools["query"]["description"]
        self.assertNotIn("description", desc)
        self.assertNotIn("tags", desc)

    def test_query_description_mentions_metadata_when_enabled(self):
        desc = make_adapter(metadata_enabled=True).tools["query"]["description"]
        self.assertIn("description", desc)
        self.assertIn("tags", desc)

    def test_metadata_disabled_flag_default_without_config_key(self):
        adapter = MinimaRestAdapter(config={"USE_MINIMA_MCP": True})
        self.assertFalse(adapter.metadata_enabled)


class TestChunkCitationFormatting(unittest.TestCase):
    def _format(self, adapter, chunks):
        return adapter._format_result_with_chunk_citations(chunks)

    def test_plain_citation_when_metadata_disabled(self):
        adapter = make_adapter(metadata_enabled=False)
        chunks = [{"content": "hello", "source": "file://doc.pdf", "metadata": {"description": "desc", "tags": ["a"]}}]
        result = self._format(adapter, chunks)
        self.assertIn("[Source: file://doc.pdf]", result["result"])
        self.assertNotIn("desc", result["result"])
        self.assertNotIn("tags:", result["result"])

    def test_citation_includes_description_when_enabled(self):
        adapter = make_adapter(metadata_enabled=True)
        chunks = [{"content": "hello", "source": "file://doc.pdf", "metadata": {"description": "my description", "tags": []}}]
        result = self._format(adapter, chunks)
        self.assertIn("my description", result["result"])
        self.assertIn("[Source: file://doc.pdf]", result["result"])

    def test_citation_includes_tags_when_enabled(self):
        adapter = make_adapter(metadata_enabled=True)
        chunks = [{"content": "hello", "source": "file://doc.pdf", "metadata": {"description": "", "tags": ["foo", "bar"]}}]
        result = self._format(adapter, chunks)
        self.assertIn("tags: foo, bar", result["result"])

    def test_citation_includes_both_desc_and_tags_when_enabled(self):
        adapter = make_adapter(metadata_enabled=True)
        chunks = [{"content": "hello", "source": "file://doc.pdf", "metadata": {"description": "my desc", "tags": ["t1"]}}]
        result = self._format(adapter, chunks)
        self.assertIn("my desc", result["result"])
        self.assertIn("tags: t1", result["result"])

    def test_citation_plain_when_enabled_but_no_metadata_field(self):
        adapter = make_adapter(metadata_enabled=True)
        chunks = [{"content": "hello", "source": "file://doc.pdf"}]
        result = self._format(adapter, chunks)
        self.assertIn("[Source: file://doc.pdf]", result["result"])
        self.assertNotIn("tags:", result["result"])

    def test_citation_plain_when_enabled_but_empty_metadata(self):
        adapter = make_adapter(metadata_enabled=True)
        chunks = [{"content": "hello", "source": "file://doc.pdf", "metadata": {"description": "", "tags": []}}]
        result = self._format(adapter, chunks)
        self.assertEqual(result["result"].strip(), "hello [Source: file://doc.pdf]")

    def test_invalid_chunk_skipped(self):
        adapter = make_adapter(metadata_enabled=False)
        chunks = [{"content": "good", "source": "file://a.pdf"}, {"bad": "chunk"}]
        result = self._format(adapter, chunks)
        self.assertIn("good", result["result"])

    def test_empty_chunks_returns_warning(self):
        adapter = make_adapter(metadata_enabled=False)
        result = self._format(adapter, [])
        self.assertIn("WARNING", result["result"])


class TestMetadataAPIEndpointGating(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import api.main as main_module
        from fastapi.testclient import TestClient

        self._orig_config = dict(main_module.config)

        main_module.config["USE_MINIMA_METADATA"] = False
        self.client = TestClient(main_module.app, raise_server_exceptions=False)
        self.main = main_module

    async def asyncTearDown(self):
        import api.main as main_module
        main_module.config.clear()
        main_module.config.update(self._orig_config)

    def test_get_metadata_blocked_when_disabled(self):
        response = self.client.get("/minima/metadata?path=/docs/file.pdf")
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("not enabled", data["message"])

    def test_put_metadata_blocked_when_disabled(self):
        response = self.client.put("/minima/metadata", json={"path": "/docs/file.pdf", "description": "x", "tags": []})
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("not enabled", data["message"])

    def test_get_files_blocked_when_disabled(self):
        response = self.client.get("/minima/files")
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("not enabled", data["message"])


if __name__ == "__main__":
    unittest.main()
