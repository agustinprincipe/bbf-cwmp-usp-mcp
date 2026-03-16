"""Tests for BBFIndexer."""
import tempfile
from pathlib import Path

import pytest

from indexer import BBFIndexer


@pytest.fixture
def sample_xml(tmp_path):
    """Create a minimal BBF data model XML for testing."""
    xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<dm:document
    xmlns:dm="urn:broadband-forum-org:cwmp:datamodel-1-15"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="urn:broadband-forum-org:cwmp:datamodel-1-15
                        https://www.broadband-forum.org/cwmp/cwmp-datamodel-1-15.xsd"
    spec="urn:broadband-forum-org:tr-181-2-20-1"
    file="tr-181-2-20-1-cwmp-full.xml">

  <model name="Device:2.20">
    <object name="Device." access="readOnly">
      <description>Top-level object.</description>
      <parameter name="RootDataModelVersion" access="readOnly">
        <description>Root data model version.</description>
        <syntax><string><size maxLength="32"/></string></syntax>
      </parameter>
    </object>
    <object name="Device.DeviceInfo." access="readOnly">
      <description>Device information.</description>
      <parameter name="Manufacturer" access="readOnly">
        <description>The manufacturer of the device.</description>
        <syntax><string><size maxLength="64"/></string></syntax>
      </parameter>
      <parameter name="ModelName" access="readOnly">
        <description>Model name of the device.</description>
        <syntax><string><size maxLength="64"/></string></syntax>
      </parameter>
    </object>
    <object name="Device.WiFi." access="readOnly">
      <description>WiFi object.</description>
    </object>
    <object name="Device.WiFi.Radio.{i}." access="readOnly" minEntries="0" maxEntries="unbounded">
      <description>WiFi radio instance.</description>
      <parameter name="Enable" access="readWrite">
        <description>Enables or disables the radio.</description>
        <syntax><boolean/></syntax>
      </parameter>
      <parameter name="Channel" access="readWrite">
        <description>Current radio channel.</description>
        <syntax><unsignedInt/></syntax>
      </parameter>
    </object>
  </model>
</dm:document>
"""
    cwmp_dir = tmp_path / "cwmp"
    cwmp_dir.mkdir()
    xml_path = cwmp_dir / "tr-181-2-20-1-cwmp-full.xml"
    xml_path.write_text(xml_content)
    return tmp_path


@pytest.fixture
def sample_markdown(tmp_path):
    """Create sample USP spec markdown files."""
    spec_dir = tmp_path / "usp-spec"
    spec_dir.mkdir()

    arch_dir = spec_dir / "architecture"
    arch_dir.mkdir()
    (arch_dir / "index.md").write_text(
        "# Architecture\n\n"
        "USP is designed as a session-based protocol.\n\n"
        "## Components\n\n"
        "An Agent is a USP endpoint that exposes a data model."
    )

    (spec_dir / "index.md").write_text(
        "# USP Specification\n\n"
        "TR-369 defines the User Services Platform."
    )
    return tmp_path


@pytest.fixture
def sample_proto(tmp_path):
    """Create sample proto files."""
    spec_dir = tmp_path / "usp-spec"
    spec_dir.mkdir(exist_ok=True)
    (spec_dir / "usp-msg-1-5.proto").write_text(
        'syntax = "proto3";\n'
        "message Msg {\n"
        "  Header header = 1;\n"
        "  Body body = 2;\n"
        "}\n"
    )
    return tmp_path


class TestBBFIndexer:
    def test_chunk_text_short(self):
        indexer = BBFIndexer.__new__(BBFIndexer)
        indexer.chunk_size = 1000
        text = "Short text."
        assert indexer._chunk_text(text) == ["Short text."]

    def test_chunk_text_splits_on_paragraphs(self):
        indexer = BBFIndexer.__new__(BBFIndexer)
        indexer.chunk_size = 50
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph that is a bit longer."
        chunks = indexer._chunk_text(text)
        assert len(chunks) >= 2
        assert all(len(c) <= 80 for c in chunks)  # some slack for boundary

    def test_make_param_doc(self):
        indexer = BBFIndexer.__new__(BBFIndexer)
        from xml_parser import DMParameter
        param = DMParameter(
            name="SSID",
            access="readWrite",
            description="The SSID string.",
            data_type="string",
            enumerations=["Open", "WPA2"],
        )
        doc = indexer._make_param_doc("Device.WiFi.SSID.{i}.", param)
        assert "Device.WiFi.SSID.{i}.SSID" in doc
        assert "readWrite" in doc
        assert "Open, WPA2" in doc

    def test_make_obj_doc(self):
        indexer = BBFIndexer.__new__(BBFIndexer)
        from xml_parser import DMObject
        obj = DMObject(
            name="Device.WiFi.",
            access="readOnly",
            description="WiFi top-level.",
            is_multi_instance=False,
        )
        doc = indexer._make_obj_doc(obj)
        assert "Device.WiFi." in doc
        assert "WiFi top-level." in doc

    def test_index_data_model(self, sample_xml):
        """Test that XML data model indexing produces ChromaDB chunks."""
        indexer = BBFIndexer(data_dir=sample_xml)
        xml_path = sample_xml / "cwmp" / "tr-181-2-20-1-cwmp-full.xml"
        count = indexer.index_data_model(xml_path, "test_cwmp_dm")
        # 4 objects + 5 parameters = 9 chunks
        assert count == 9

        # Verify the collection exists and has data
        import chromadb
        client = chromadb.PersistentClient(path=str(sample_xml / "vector_db"))
        col = client.get_collection("test_cwmp_dm")
        assert col.count() == 9

    def test_index_markdown_dir(self, sample_markdown):
        """Test markdown file indexing."""
        indexer = BBFIndexer(data_dir=sample_markdown)
        spec_dir = sample_markdown / "usp-spec"
        count = indexer.index_markdown_dir(spec_dir, "test_usp_spec")
        assert count > 0

        import chromadb
        client = chromadb.PersistentClient(path=str(sample_markdown / "vector_db"))
        col = client.get_collection("test_usp_spec")
        assert col.count() == count

    def test_index_schema_files(self, sample_proto):
        """Test proto file indexing."""
        indexer = BBFIndexer(data_dir=sample_proto)
        protos = list((sample_proto / "usp-spec").glob("*.proto"))
        count = indexer.index_schema_files(protos, "test_usp_proto")
        assert count > 0

    def test_index_schema_files_empty(self, tmp_path):
        """Test with no files."""
        indexer = BBFIndexer(data_dir=tmp_path)
        count = indexer.index_schema_files([], "test_empty")
        assert count == 0
