# MCP Server Current Architecture

## Stack
- Python 3.13+, MCP SDK 1.16.0, ChromaDB, sentence-transformers (all-MiniLM-L6-v2)
- Entry: main.py -> server.py (MCP server with 6 search tools)
- Indexer: indexer.py (UnifiedTRIndexer class)

## Data Flow
1. PDFs placed manually in data/{tr069,tr369,shared}/{standards,data_models,protocols}/
2. indexer.py converts PDFs to markdown (docling), chunks text, generates embeddings, stores in ChromaDB
3. server.py loads ChromaDB collections and serves semantic search via MCP tools

## Key Files
- server.py: `init_vector_store()`, `list_tools()` (6 tools), `call_tool()` (search handler)
- indexer.py: `UnifiedTRIndexer` with convert_pdfs_to_markdown, index_markdown_files, index_protocol_files
- Collections: tr069_standards, tr069_data_models, tr069_protocols, tr369_standards, tr369_protocols, shared_data_models

## Modules
- bbf_fetcher.py: `BBFDataFetcher` — discovers + downloads BBF files from GitHub (Trees API + raw download)
- xml_parser.py: `BBFXMLParser` — parses BBF data model XMLs into `DataModel` (objects, parameters, types, constraints)
- indexer.py: `BBFIndexer` — indexes data models, USP spec markdown, and protocol schemas into ChromaDB
  - Collections: cwmp_datamodel (10,651), usp_datamodel (8,244), usp_spec (218), cwmp_protocols (3), usp_protocols (7)
- server.py: MCP server with 5 tools:
  - search_datamodel (semantic, protocol filter)
  - get_parameter (exact path lookup, in-memory DataModel)
  - list_objects (tree navigation, in-memory DataModel)
  - search_usp_spec (semantic over TR-369 spec)
  - search_protocol_schema (semantic over XSD/proto, protocol filter)
- CLI: `python main.py init` (fetch), `python main.py index` (index), `python main.py serve` (MCP server)

## Known Limitations
- docling removed, no longer processes PDFs
- No incremental update yet (init + index are full re-runs)
- list_children depth counting doesn't handle {i} in paths as expected (multi-instance objects appear deeper than they are)