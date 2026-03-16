"""Tests for server tool handlers."""
import json

import pytest

from xml_parser import DMParameter, DMObject, DataModel
import server


@pytest.fixture(autouse=True)
def setup_data_models():
    """Set up in-memory data models for testing."""
    dm = DataModel(name="Device:2.20")
    dm.objects["Device."] = DMObject(
        name="Device.",
        access="readOnly",
        description="Top-level object.",
        parameters={
            "RootDataModelVersion": DMParameter(
                name="RootDataModelVersion",
                access="readOnly",
                description="Root version.",
                data_type="string",
            )
        },
    )
    dm.objects["Device.DeviceInfo."] = DMObject(
        name="Device.DeviceInfo.",
        access="readOnly",
        description="Device information.",
        parameters={
            "Manufacturer": DMParameter(
                name="Manufacturer",
                access="readOnly",
                description="The manufacturer.",
                data_type="string",
            ),
            "ModelName": DMParameter(
                name="ModelName",
                access="readOnly",
                description="Model name.",
                data_type="string",
            ),
        },
    )
    dm.objects["Device.WiFi."] = DMObject(
        name="Device.WiFi.",
        access="readOnly",
        description="WiFi top-level.",
    )
    dm.objects["Device.WiFi.Radio.{i}."] = DMObject(
        name="Device.WiFi.Radio.{i}.",
        access="readOnly",
        description="WiFi radio.",
        is_multi_instance=True,
        max_entries="unbounded",
        parameters={
            "Enable": DMParameter(
                name="Enable",
                access="readWrite",
                description="Enable radio.",
                data_type="boolean",
            ),
        },
    )

    server.data_models["cwmp"] = dm
    yield
    server.data_models.clear()


class TestGetParameter:
    def test_get_existing_parameter(self):
        result = server._tool_get_parameter({"path": "Device.DeviceInfo.Manufacturer", "protocol": "cwmp"})
        data = json.loads(result)
        assert data["path"] == "Device.DeviceInfo.Manufacturer"
        assert data["type"] == "string"
        assert data["access"] == "readOnly"

    def test_get_existing_object(self):
        result = server._tool_get_parameter({"path": "Device.DeviceInfo.", "protocol": "cwmp"})
        data = json.loads(result)
        assert data["path"] == "Device.DeviceInfo."
        assert "parameters" in data
        assert len(data["parameters"]) == 2

    def test_get_object_without_trailing_dot(self):
        result = server._tool_get_parameter({"path": "Device.DeviceInfo", "protocol": "cwmp"})
        data = json.loads(result)
        assert data["path"] == "Device.DeviceInfo."

    def test_get_nonexistent(self):
        result = server._tool_get_parameter({"path": "Device.Foo.Bar", "protocol": "cwmp"})
        assert "not found" in result

    def test_get_no_protocol(self):
        result = server._tool_get_parameter({"path": "Device.", "protocol": "nonexistent"})
        assert "No data model" in result


class TestListObjects:
    def test_list_device_children(self):
        result = server._tool_list_objects({"path": "Device.", "protocol": "cwmp"})
        data = json.loads(result)
        assert data["parent"] == "Device."
        child_paths = [c["path"] for c in data["children"]]
        assert "Device.DeviceInfo." in child_paths
        assert "Device.WiFi." in child_paths

    def test_list_wifi_children(self):
        # Device.WiFi.Radio.{i}. is 2 levels deep (Radio + {i}), not a direct child
        result = server._tool_list_objects({"path": "Device.WiFi.", "protocol": "cwmp"})
        assert "No child objects" in result

    def test_list_with_params(self):
        # DeviceInfo. has no child objects, but we can test include_params on Device.
        result = server._tool_list_objects({
            "path": "Device.",
            "protocol": "cwmp",
            "include_params": True,
        })
        data = json.loads(result)
        assert "parameters" in data
        assert len(data["parameters"]) == 1  # RootDataModelVersion

    def test_list_no_children(self):
        result = server._tool_list_objects({"path": "Device.WiFi.Radio.{i}.", "protocol": "cwmp"})
        assert "No child objects" in result

    def test_list_without_trailing_dot(self):
        result = server._tool_list_objects({"path": "Device", "protocol": "cwmp"})
        data = json.loads(result)
        assert data["parent"] == "Device."


class TestHandleTool:
    def test_unknown_tool(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            server._handle_tool("nonexistent_tool", {})

    def test_search_datamodel_no_collections(self):
        result = server._tool_search_datamodel({"query": "wifi", "protocol": "cwmp"})
        # No ChromaDB collections loaded, should indicate not available
        assert "not available" in result or "No results" in result
