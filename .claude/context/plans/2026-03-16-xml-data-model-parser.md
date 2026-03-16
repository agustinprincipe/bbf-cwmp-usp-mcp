---
task: Sub-tarea 2 — XML Data Model Parser
date: 2026-03-16
mode: directo
steps: 4
analysis_file: .claude/context/analysis/2026-03-16-bbf-github-source-of-truth.md
---

## Plan de Implementacion: XML Data Model Parser

### Contexto

Los XMLs de BBF usan namespace `urn:broadband-forum-org:cwmp:datamodel-1-15`:
- `<dm:document>` root con `<model>`
- `<object name="Device.WiFi.SSID.{i}.">` — jerarquia plana en `name`, trailing dot
- `<parameter name="SSID">` dentro de cada object — con `<description>`, `<syntax>`, `access`, `version`
- Tipos: `<string>`, `<unsignedInt>`, `<boolean>`, `<dataType ref="...">`, con constraints

### Archivos

**`xml_parser.py`** (NUEVO)
- Dataclasses: `DMParameter`, `DMObject`, `DataModel`
- `BBFXMLParser.parse(xml_path) -> DataModel`
- Usa `xml.etree.ElementTree` (stdlib)

**`tests/test_xml_parser.py`** (NUEVO)
- Tests con XML fixture inline

### Pasos

1. Crear dataclasses (`DMParameter`, `DMObject`, `DataModel`) + `BBFXMLParser` esqueleto
2. Implementar `parse()` — extract objects + parameters con metadata
3. Tests con XML fixture inline (version parsing, tipo extraction, jerarquia)
4. Verificar con datos reales en `data/cwmp/`
