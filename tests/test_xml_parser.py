"""Tests for BBF XML data model parser."""

import pytest

from xml_parser import BBFXMLParser, DMParameter, DMObject, DataModel


SAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<dm:document
    xmlns:dm="urn:broadband-forum-org:cwmp:datamodel-1-15"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    spec="urn:broadband-forum-org:tr-181-2-20-1-cwmp"
    file="tr-181-2-20-1-cwmp.xml">

  <model name="Device:2.20">
    <object name="Device." access="readOnly" minEntries="1" maxEntries="1" version="2.0">
      <description>The top-level object for a Device.</description>
    </object>

    <object name="Device.DeviceInfo." access="readOnly" minEntries="1" maxEntries="1" version="2.0">
      <description>This object contains general device information.</description>
      <parameter name="Manufacturer" access="readOnly">
        <description>The manufacturer of the CPE (human readable string).</description>
        <syntax>
          <string><size maxLength="64"/></string>
        </syntax>
      </parameter>
      <parameter name="ManufacturerOUI" access="readOnly">
        <description>Organizationally unique identifier of the device manufacturer.</description>
        <syntax>
          <string>
            <size minLength="6" maxLength="6"/>
            <pattern value="[0-9A-F]{6}"/>
          </string>
        </syntax>
      </parameter>
      <parameter name="SerialNumber" access="readOnly" version="2.0" forcedInform="true">
        <description>Serial number of the CPE.</description>
        <syntax>
          <string><size maxLength="64"/></string>
        </syntax>
      </parameter>
    </object>

    <object name="Device.WiFi." access="readOnly" minEntries="1" maxEntries="1" version="2.0">
      <description>The WiFi object is based on the WiFi Alliance 802.11 specification.</description>
      <parameter name="RadioNumberOfEntries" access="readOnly">
        <description>The number of entries in the Radio table.</description>
        <syntax><unsignedInt/></syntax>
      </parameter>
      <parameter name="SSIDNumberOfEntries" access="readOnly">
        <description>The number of entries in the SSID table.</description>
        <syntax><unsignedInt/></syntax>
      </parameter>
    </object>

    <object name="Device.WiFi.SSID.{i}." access="readWrite"
        numEntriesParameter="SSIDNumberOfEntries" minEntries="0"
        maxEntries="unbounded" version="2.0">
      <description>WiFi SSID table, where table entries model the MAC layer.</description>
      <uniqueKey functional="false">
        <parameter ref="Alias"/>
      </uniqueKey>
      <parameter name="Enable" access="readWrite">
        <description>Enables or disables the interface.</description>
        <syntax>
          <boolean/>
          <default type="object" value="false"/>
        </syntax>
      </parameter>
      <parameter name="Status" access="readOnly" version="2.0">
        <description>The current operational state of the interface.</description>
        <syntax>
          <string>
            <enumeration value="Up"/>
            <enumeration value="Down"/>
            <enumeration value="Unknown"/>
            <enumeration value="Dormant"/>
            <enumeration value="NotPresent"/>
            <enumeration value="LowerLayerDown"/>
            <enumeration value="Error" optional="true"/>
          </string>
          <default type="object" value="Down"/>
        </syntax>
      </parameter>
      <parameter name="SSID" access="readWrite">
        <description>The current service set identifier in use by the connection.</description>
        <syntax>
          <string><size maxLength="32"/></string>
        </syntax>
      </parameter>
      <parameter name="MACAddress" access="readOnly">
        <description>The MAC address of the interface.</description>
        <syntax>
          <dataType ref="MACAddress"/>
        </syntax>
      </parameter>
    </object>

    <object name="Device.WiFi.SSID.{i}.Stats." access="readOnly" minEntries="1"
        maxEntries="1" version="2.0">
      <description>Throughput statistics for this interface.</description>
      <parameter name="BytesSent" access="readOnly" activeNotify="canDeny">
        <description>The total number of bytes transmitted.</description>
        <syntax>
          <unsignedLong/>
        </syntax>
      </parameter>
      <parameter name="RetransCount" access="readOnly" version="2.8">
        <description>The total number of retransmissions.</description>
        <syntax>
          <unsignedInt>
            <range minInclusive="0" maxInclusive="4294967295"/>
            <units value="packets"/>
          </unsignedInt>
        </syntax>
      </parameter>
    </object>
  </model>
</dm:document>
"""


@pytest.fixture
def parser():
    return BBFXMLParser()


@pytest.fixture
def data_model(parser, tmp_path):
    xml_file = tmp_path / "test-model.xml"
    xml_file.write_text(SAMPLE_XML)
    return parser.parse(xml_file)


class TestDataModelParsing:
    def test_model_name(self, data_model):
        assert data_model.name == "Device:2.20"

    def test_objects_count(self, data_model):
        # Device, DeviceInfo, WiFi, WiFi.SSID.{i}, WiFi.SSID.{i}.Stats
        assert len(data_model.objects) == 5

    def test_root_object(self, data_model):
        obj = data_model.objects["Device."]
        assert obj.name == "Device."
        assert obj.access == "readOnly"
        assert obj.version == "2.0"
        assert "top-level" in obj.description

    def test_object_with_parameters(self, data_model):
        obj = data_model.objects["Device.DeviceInfo."]
        assert len(obj.parameters) == 3
        assert "Manufacturer" in obj.parameters
        assert "SerialNumber" in obj.parameters

    def test_parameter_basic(self, data_model):
        param = data_model.objects["Device.DeviceInfo."].parameters["Manufacturer"]
        assert param.name == "Manufacturer"
        assert param.access == "readOnly"
        assert param.data_type == "string"
        assert "manufacturer" in param.description.lower()

    def test_parameter_string_constraints(self, data_model):
        param = data_model.objects["Device.DeviceInfo."].parameters["ManufacturerOUI"]
        assert param.data_type == "string"
        assert param.max_length == 6
        assert param.min_length == 6
        assert param.pattern == "[0-9A-F]{6}"

    def test_parameter_boolean(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}."].parameters["Enable"]
        assert param.data_type == "boolean"
        assert param.access == "readWrite"
        assert param.default == "false"

    def test_parameter_enumeration(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}."].parameters["Status"]
        assert param.data_type == "string"
        assert param.enumerations == ["Up", "Down", "Unknown", "Dormant",
                                      "NotPresent", "LowerLayerDown", "Error"]

    def test_parameter_datatype_ref(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}."].parameters["MACAddress"]
        assert param.data_type == "MACAddress"

    def test_parameter_unsigned_int_with_range(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}.Stats."].parameters["RetransCount"]
        assert param.data_type == "unsignedInt"
        assert param.range_min == 0
        assert param.range_max == 4294967295
        assert param.units == "packets"

    def test_parameter_unsigned_long(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}.Stats."].parameters["BytesSent"]
        assert param.data_type == "unsignedLong"

    def test_parameter_version(self, data_model):
        param = data_model.objects["Device.WiFi.SSID.{i}.Stats."].parameters["RetransCount"]
        assert param.version == "2.8"

    def test_multi_instance_object(self, data_model):
        obj = data_model.objects["Device.WiFi.SSID.{i}."]
        assert obj.is_multi_instance is True
        assert obj.max_entries == "unbounded"

    def test_single_instance_object(self, data_model):
        obj = data_model.objects["Device.DeviceInfo."]
        assert obj.is_multi_instance is False


class TestDataModelQueries:
    def test_get_object(self, data_model):
        obj = data_model.get_object("Device.WiFi.")
        assert obj is not None
        assert obj.name == "Device.WiFi."

    def test_get_object_not_found(self, data_model):
        assert data_model.get_object("Device.NonExistent.") is None

    def test_get_parameter(self, data_model):
        param = data_model.get_parameter("Device.DeviceInfo.Manufacturer")
        assert param is not None
        assert param.name == "Manufacturer"

    def test_get_parameter_not_found(self, data_model):
        assert data_model.get_parameter("Device.DeviceInfo.NotAParam") is None

    def test_list_children(self, data_model):
        children = data_model.list_children("Device.")
        child_names = [c.name for c in children]
        assert "Device.DeviceInfo." in child_names
        assert "Device.WiFi." in child_names
        assert "Device.WiFi.SSID.{i}." not in child_names  # not direct child of Device.

    def test_list_children_of_table(self, data_model):
        children = data_model.list_children("Device.WiFi.SSID.{i}.")
        child_names = [c.name for c in children]
        assert "Device.WiFi.SSID.{i}.Stats." in child_names

    def test_search_by_keyword(self, data_model):
        results = data_model.search("manufacturer")
        # Should find both the object description and the parameter
        paths = [r["path"] for r in results]
        assert "Device.DeviceInfo.Manufacturer" in paths

    def test_search_by_path_fragment(self, data_model):
        results = data_model.search("WiFi.SSID")
        paths = [r["path"] for r in results]
        assert any("WiFi.SSID" in p for p in paths)
