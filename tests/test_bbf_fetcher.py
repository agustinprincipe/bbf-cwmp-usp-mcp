"""Tests for BBF data fetcher."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from bbf_fetcher import BBFDataFetcher, InitResult


@pytest.fixture
def fetcher():
    return BBFDataFetcher()


@pytest.fixture
def cwmp_tree_response():
    """Simulated GitHub Trees API response for cwmp-data-models."""
    return {
        "sha": "abc123",
        "tree": [
            {"path": "tr-181-2-18-0-cwmp-full.xml", "type": "blob", "size": 4500000},
            {"path": "tr-181-2-19-0-cwmp-full.xml", "type": "blob", "size": 4600000},
            {"path": "tr-181-2-20-1-cwmp-full.xml", "type": "blob", "size": 4900000},
            {"path": "tr-098-1-7-0-full.xml", "type": "blob", "size": 2000000},
            {"path": "tr-098-1-8-0-full.xml", "type": "blob", "size": 2100000},
            {"path": "cwmp-1-3.xsd", "type": "blob", "size": 50000},
            {"path": "cwmp-1-4.xsd", "type": "blob", "size": 55000},
            {"path": "README.md", "type": "blob", "size": 5000},
            {"path": "components", "type": "tree"},
            {"path": "components/tr-181-2-20-1-wifi-cwmp.xml", "type": "blob", "size": 100000},
        ],
    }


@pytest.fixture
def usp_dm_tree_response():
    """Simulated GitHub Trees API response for usp-data-models."""
    return {
        "sha": "def456",
        "tree": [
            {"path": "tr-181-2-19-0-usp-full.xml", "type": "blob", "size": 4500000},
            {"path": "tr-181-2-20-1-usp-full.xml", "type": "blob", "size": 4800000},
            {"path": "README.md", "type": "blob", "size": 3000},
        ],
    }


@pytest.fixture
def usp_spec_tree_response():
    """Simulated GitHub Trees API response for usp repo."""
    return {
        "sha": "ghi789",
        "tree": [
            {"path": "specification/architecture/index.md", "type": "blob", "size": 20000},
            {"path": "specification/messages/index.md", "type": "blob", "size": 30000},
            {"path": "specification/mtp/stomp/index.md", "type": "blob", "size": 15000},
            {"path": "specification/usp-msg-1-4.proto", "type": "blob", "size": 8000},
            {"path": "specification/usp-msg-1-5.proto", "type": "blob", "size": 9000},
            {"path": "specification/usp-record-1-4.proto", "type": "blob", "size": 6000},
            {"path": "specification/usp-record-1-5.proto", "type": "blob", "size": 7000},
            {"path": "README.md", "type": "blob", "size": 5000},
        ],
    }


class TestVersionParsing:
    def test_parse_cwmp_full_version(self, fetcher):
        v = fetcher._parse_version("tr-181-2-20-1-cwmp-full.xml")
        assert v == (181, 2, 20, 1)

    def test_parse_tr098_version(self, fetcher):
        v = fetcher._parse_version("tr-098-1-8-0-full.xml")
        assert v == (98, 1, 8, 0)

    def test_parse_usp_full_version(self, fetcher):
        v = fetcher._parse_version("tr-181-2-20-1-usp-full.xml")
        assert v == (181, 2, 20, 1)

    def test_parse_xsd_version(self, fetcher):
        v = fetcher._parse_version("cwmp-1-4.xsd")
        assert v == (1, 4)

    def test_parse_proto_version(self, fetcher):
        v = fetcher._parse_version("usp-msg-1-5.proto")
        assert v == (1, 5)

    def test_version_comparison(self, fetcher):
        v1 = fetcher._parse_version("tr-181-2-18-0-cwmp-full.xml")
        v2 = fetcher._parse_version("tr-181-2-20-1-cwmp-full.xml")
        assert v2 > v1


class TestDiscoverFiles:
    @pytest.mark.asyncio
    async def test_discover_cwmp_latest_full(self, fetcher, cwmp_tree_response):
        mock_response = AsyncMock()
        mock_response.json = lambda: cwmp_tree_response
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await fetcher.discover_files("cwmp-data-models")

        # Should select only the latest version of each pattern
        assert "tr-181-2-20-1-cwmp-full.xml" in result["data_models"]
        assert "tr-181-2-18-0-cwmp-full.xml" not in result["data_models"]
        assert "tr-181-2-19-0-cwmp-full.xml" not in result["data_models"]
        assert "tr-098-1-8-0-full.xml" in result["data_models"]
        assert "tr-098-1-7-0-full.xml" not in result["data_models"]
        assert "cwmp-1-4.xsd" in result["protocols"]
        assert "cwmp-1-3.xsd" not in result["protocols"]

    @pytest.mark.asyncio
    async def test_discover_usp_dm_latest(self, fetcher, usp_dm_tree_response):
        mock_response = AsyncMock()
        mock_response.json = lambda: usp_dm_tree_response
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await fetcher.discover_files("usp-data-models")

        assert "tr-181-2-20-1-usp-full.xml" in result["data_models"]
        assert "tr-181-2-19-0-usp-full.xml" not in result["data_models"]

    @pytest.mark.asyncio
    async def test_discover_usp_spec(self, fetcher, usp_spec_tree_response):
        mock_response = AsyncMock()
        mock_response.json = lambda: usp_spec_tree_response
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await fetcher.discover_files("usp")

        # All markdown files should be included (not latest_only for md)
        assert "specification/architecture/index.md" in result["spec_markdown"]
        assert "specification/messages/index.md" in result["spec_markdown"]
        assert "specification/mtp/stomp/index.md" in result["spec_markdown"]
        # Only latest proto versions
        assert "specification/usp-msg-1-5.proto" in result["protocols"]
        assert "specification/usp-msg-1-4.proto" not in result["protocols"]
        assert "specification/usp-record-1-5.proto" in result["protocols"]
        assert "specification/usp-record-1-4.proto" not in result["protocols"]


class TestRunInit:
    @pytest.mark.asyncio
    async def test_run_init_creates_manifest(self, fetcher, tmp_path, cwmp_tree_response, usp_dm_tree_response, usp_spec_tree_response):
        tree_responses = {
            "cwmp-data-models": cwmp_tree_response,
            "usp-data-models": usp_dm_tree_response,
            "usp": usp_spec_tree_response,
        }

        async def mock_get(url, **kwargs):
            resp = AsyncMock()
            resp.raise_for_status = lambda: None
            for repo_name, tree_data in tree_responses.items():
                if repo_name in url and "git/trees" in url:
                    resp.json = lambda td=tree_data: td
                    return resp
            # For raw download requests, return dummy content
            resp.content = b"<xml>dummy</xml>"
            resp.text = "dummy content"
            return resp

        def mock_stream(method, url, **kwargs):
            class FakeStream:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                def raise_for_status(self):
                    pass
                async def aiter_bytes(self):
                    yield b"<xml>dummy content</xml>"
            return FakeStream()

        with patch("httpx.AsyncClient.get", side_effect=mock_get), \
             patch("httpx.AsyncClient.stream", side_effect=mock_stream):
            result = await fetcher.run_init(tmp_path)

        assert isinstance(result, InitResult)
        assert result.total_files > 0

        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "repos" in manifest
        assert "cwmp-data-models" in manifest["repos"]

        # Check directory structure
        assert (tmp_path / "cwmp").is_dir()
        assert (tmp_path / "usp").is_dir()
        assert (tmp_path / "usp-spec").is_dir()