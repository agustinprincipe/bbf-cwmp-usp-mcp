"""
Parser for Broadband Forum XML data model files.

Parses the structured XML format used in TR-181, TR-098 and other BBF data models,
extracting objects, parameters, types, and metadata into Python dataclasses.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


# BBF data model XML namespace
DM_NS = "urn:broadband-forum-org:cwmp:datamodel-1-15"
NS = {"dm": DM_NS}


@dataclass
class DMParameter:
    """A data model parameter (leaf node)."""

    name: str
    access: str = "readOnly"
    description: str = ""
    data_type: str = "string"
    version: str = ""
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    range_min: int | None = None
    range_max: int | None = None
    units: str | None = None
    enumerations: list[str] = field(default_factory=list)
    default: str | None = None


@dataclass
class DMObject:
    """A data model object (container node)."""

    name: str
    access: str = "readOnly"
    description: str = ""
    version: str = ""
    min_entries: str = "1"
    max_entries: str = "1"
    is_multi_instance: bool = False
    parameters: dict[str, DMParameter] = field(default_factory=dict)


@dataclass
class DataModel:
    """Parsed BBF data model with query capabilities."""

    name: str
    objects: dict[str, DMObject] = field(default_factory=dict)

    def get_object(self, path: str) -> DMObject | None:
        return self.objects.get(path)

    def get_parameter(self, path: str) -> DMParameter | None:
        """Get parameter by full path like 'Device.DeviceInfo.Manufacturer'."""
        # Split into object path + parameter name
        parts = path.rsplit(".", 1)
        if len(parts) != 2:
            return None
        obj_path = parts[0] + "."
        param_name = parts[1]
        obj = self.objects.get(obj_path)
        if obj is None:
            return None
        return obj.parameters.get(param_name)

    def list_children(self, parent_path: str) -> list[DMObject]:
        """List direct child objects of a given path."""
        children = []
        parent_depth = parent_path.count(".")
        for name, obj in self.objects.items():
            if name == parent_path:
                continue
            if not name.startswith(parent_path):
                continue
            # Direct child: one more dot level (accounting for trailing dot)
            # e.g. parent "Device." (depth 1), child "Device.WiFi." (depth 2)
            child_depth = name.rstrip(".").count(".") + 1
            if child_depth == parent_depth + 1:
                children.append(obj)
        return children

    def search(self, query: str) -> list[dict]:
        """Search objects and parameters by keyword in name or description."""
        query_lower = query.lower()
        results = []

        for obj_name, obj in self.objects.items():
            if query_lower in obj_name.lower() or query_lower in obj.description.lower():
                results.append({
                    "path": obj_name,
                    "type": "object",
                    "description": obj.description,
                })
            for param_name, param in obj.parameters.items():
                full_path = obj_name.rstrip(".") + "." + param_name
                if query_lower in full_path.lower() or query_lower in param.description.lower():
                    results.append({
                        "path": full_path,
                        "type": "parameter",
                        "data_type": param.data_type,
                        "access": param.access,
                        "description": param.description,
                    })

        return results


class BBFXMLParser:
    """Parses BBF data model XML files into DataModel instances."""

    def parse(self, xml_path: Path) -> DataModel:
        """Parse a BBF data model XML file."""
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Find <model> element — BBF XMLs use dm: prefix on root but NOT on children
        model_el = root.find("model")
        if model_el is None:
            # Try with namespace in case some files use it consistently
            ns = self._detect_namespace(root)
            if ns:
                model_el = root.find(f"{{{ns}}}model")

        model_name = model_el.get("name", "unknown") if model_el is not None else "unknown"
        data_model = DataModel(name=model_name)

        if model_el is None:
            return data_model

        # Parse all <object> elements (un-prefixed in BBF XMLs)
        for obj_el in model_el.iter("object"):
            obj = self._parse_object(obj_el)
            data_model.objects[obj.name] = obj

        return data_model

    def _detect_namespace(self, root: ET.Element) -> str | None:
        """Detect the data model namespace from the root element tag."""
        tag = root.tag
        if tag.startswith("{"):
            return tag[1:tag.index("}")]
        return None

    def _parse_object(self, el: ET.Element) -> DMObject:
        """Parse an <object> element."""
        name = el.get("name", "")

        obj = DMObject(
            name=name,
            access=el.get("access", "readOnly"),
            version=el.get("version", ""),
            min_entries=el.get("minEntries", "1"),
            max_entries=el.get("maxEntries", "1"),
            is_multi_instance="{i}" in name,
        )

        # Description
        desc_el = el.find("description")
        if desc_el is not None and desc_el.text:
            obj.description = desc_el.text.strip()

        # Parameters (only direct children with 'name' attribute, skip <parameter ref="..."/>)
        for param_el in el.findall("parameter"):
            if param_el.get("name"):
                param = self._parse_parameter(param_el)
                obj.parameters[param.name] = param

        return obj

    def _parse_parameter(self, el: ET.Element) -> DMParameter:
        """Parse a <parameter> element."""
        param = DMParameter(
            name=el.get("name", ""),
            access=el.get("access", "readOnly"),
            version=el.get("version", ""),
        )

        # Description
        desc_el = el.find("description")
        if desc_el is not None and desc_el.text:
            param.description = desc_el.text.strip()

        # Syntax
        syntax_el = el.find("syntax")
        if syntax_el is not None:
            self._parse_syntax(syntax_el, param)

        return param

    def _parse_syntax(self, syntax_el: ET.Element, param: DMParameter) -> None:
        """Parse the <syntax> element of a parameter."""
        # Detect type from the first child that is a type element
        type_elements = [
            "string", "unsignedInt", "unsignedLong", "int", "long",
            "boolean", "dateTime", "base64", "hexBinary", "dataType",
        ]

        for type_name in type_elements:
            type_el = syntax_el.find(type_name)
            if type_el is not None:
                if type_name == "dataType":
                    param.data_type = type_el.get("ref", "dataType")
                else:
                    param.data_type = type_name
                self._parse_type_constraints(type_el, param)
                break

        # List type wraps another type
        list_el = syntax_el.find("list")
        if list_el is not None and param.data_type == "string":
            for type_name in type_elements:
                inner = list_el.find(type_name)
                if inner is not None:
                    param.data_type = type_name
                    self._parse_type_constraints(inner, param)
                    break

        # Default value
        default_el = syntax_el.find("default")
        if default_el is not None:
            param.default = default_el.get("value")

    def _parse_type_constraints(self, type_el: ET.Element, param: DMParameter) -> None:
        """Parse constraints within a type element (size, range, enumeration, pattern, units)."""
        # Size constraints
        size_el = type_el.find("size")
        if size_el is not None:
            min_len = size_el.get("minLength")
            max_len = size_el.get("maxLength")
            if min_len is not None:
                param.min_length = int(min_len)
            if max_len is not None:
                param.max_length = int(max_len)

        # Range constraints
        range_el = type_el.find("range")
        if range_el is not None:
            min_val = range_el.get("minInclusive")
            max_val = range_el.get("maxInclusive")
            if min_val is not None:
                param.range_min = int(min_val)
            if max_val is not None:
                param.range_max = int(max_val)

        # Pattern
        pattern_el = type_el.find("pattern")
        if pattern_el is not None:
            param.pattern = pattern_el.get("value")

        # Units
        units_el = type_el.find("units")
        if units_el is not None:
            param.units = units_el.get("value")

        # Enumerations
        for enum_el in type_el.findall("enumeration"):
            value = enum_el.get("value")
            if value is not None:
                param.enumerations.append(value)
