---
task: Sub-tarea 3+4 — Nuevo Indexer + Nuevo Server
date: 2026-03-16
mode: directo
steps: 6
analysis_file: .claude/context/analysis/2026-03-16-bbf-github-source-of-truth.md
---

## Plan de Implementacion: Nuevo Indexer + Server

### Pasos

1. `pyproject.toml` — quitar docling
2. `indexer.py` — reescribir con BBFIndexer (index_data_models, index_usp_spec, index_protocol_schemas)
3. `server.py` — reescribir con nuevos tools (search_datamodel, get_parameter, list_objects, search_usp_spec, search_protocol_schema) + DataModel in-memory
4. `main.py` — agregar subcomando `index`
5. `tests/test_indexer.py` — tests
6. Verificacion con datos reales

### Colecciones ChromaDB
- cwmp_datamodel — Device:2 CWMP + TR-098
- usp_datamodel — Device:2 USP
- usp_spec — USP specification markdown
- cwmp_protocols — CWMP XSD schemas
- usp_protocols — USP protobuf definitions

### Server Tools
- search_datamodel (semantic, filtro protocol)
- get_parameter (exact path, in-memory DataModel)
- list_objects (tree nav, in-memory DataModel)
- search_usp_spec (semantic)
- search_protocol_schema (semantic, filtro protocol)

### Decisiones
- DataModel in-memory para lookups deterministas
- Quitar docling (no mas PDFs)
- Vector DB en data/vector_db/
