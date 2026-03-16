# BBF CWMP/USP MCP Server

MCP server for querying Broadband Forum data models and protocol specifications. Fetches official BBF data from GitHub, indexes it with embeddings, and exposes 7 tools for semantic search, exact parameter lookup, and tree navigation.

## Quick Start

### As a Claude Code Plugin (recommended)

Inside Claude Code, run:
```
/plugin marketplace add agustinprincipe/claude-plugins
/plugin install bbf-cwmp-usp@claude-plugins
```

Or with the full SSH URL:
```
/plugin marketplace add git@github.com:agustinprincipe/claude-plugins.git
/plugin install bbf-cwmp-usp@claude-plugins
```

The MCP server auto-starts with Claude Code. On first use, run the setup tools from within Claude:
- `init_data` — fetches BBF data from GitHub (~12MB)
- `index_data` — indexes into vector DB (~5 min)

### Manual Setup

```bash
git clone git@github.com:agustinprincipe/claude-plugins.git
cd bbf-cwmp-usp-mcp
uv sync
uv run python main.py init     # fetch data
uv run python main.py index    # index data
uv run python main.py serve    # start MCP server
```

## What Gets Indexed

All data is fetched automatically from official [Broadband Forum GitHub repos](https://github.com/BroadbandForum):

| Source | Content | Size |
|--------|---------|------|
| `cwmp-data-models` | TR-181 Device:2 (CWMP) + TR-098 IGD | ~6MB |
| `usp-data-models` | TR-181 Device:2 (USP) | ~5MB |
| `usp` | TR-369 spec markdown + protobuf schemas | ~1MB |

Total: ~12MB of targeted downloads (vs ~209MB if cloning full repos).

## Tools

### Query Tools

| Tool | Description |
|------|-------------|
| `search_datamodel` | Semantic search over data model objects and parameters. Filter by `protocol` (cwmp/usp). |
| `get_parameter` | Exact lookup by path (e.g. `Device.WiFi.SSID.{i}.SSID`). Returns type, access, constraints. |
| `list_objects` | List child objects of a path (e.g. `Device.WiFi.`). Tree navigation. |
| `search_usp_spec` | Search USP (TR-369) specification — architecture, messages, MTPs, security. |
| `search_protocol_schema` | Search XSD (CWMP) and protobuf (USP) message schemas. |

### Setup Tools

| Tool | Description |
|------|-------------|
| `init_data` | Fetch BBF data from GitHub. Run once, or to update. |
| `index_data` | Index fetched data into ChromaDB. Run after init. |

### Examples

```
# Find WiFi parameters by concept
search_datamodel(query="WiFi channel configuration", protocol="cwmp")

# Exact parameter lookup
get_parameter(path="Device.WiFi.Radio.{i}.Channel", protocol="cwmp")

# Browse data model tree
list_objects(path="Device.", protocol="cwmp", include_params=false)

# USP spec
search_usp_spec(query="Notify message subscription mechanism")

# Protocol schemas
search_protocol_schema(query="Inform RPC", protocol="cwmp")
```

## Architecture

```
bbf-cwmp-usp-mcp/
├── .claude-plugin/plugin.json   # Claude Code plugin manifest
├── .mcp.json                    # MCP server auto-config
├── skills/                      # Bundled skill for tool guidance
├── main.py                      # CLI: init, index, serve
├── server.py                    # MCP server (7 tools)
├── indexer.py                   # BBFIndexer — XML + markdown + schema indexing
├── xml_parser.py                # BBFXMLParser — structured XML extraction
├── bbf_fetcher.py               # BBFDataFetcher — GitHub API discovery + download
├── pyproject.toml               # Dependencies
└── data/                        # Downloaded + indexed data (gitignored)
    ├── cwmp/                    #   TR-181 CWMP + TR-098 XMLs + XSD
    ├── usp/                     #   TR-181 USP XML
    ├── usp-spec/                #   TR-369 spec markdown + protobuf
    ├── vector_db/               #   ChromaDB embeddings
    └── manifest.json            #   Download metadata
```

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Internet connection (for `init` only)

## Dependencies

- `mcp` — Model Context Protocol SDK
- `chromadb` — Vector database
- `sentence-transformers` — Embedding model (all-MiniLM-L6-v2)
- `httpx` — HTTP client for GitHub API

## Data Coverage

After indexing, the server contains:

- **~1,850 objects** and **~15,000 parameters** from TR-181 Device:2 and TR-098
- **20 markdown files** from the USP specification
- **CWMP XSD** and **USP protobuf** schema definitions
- **~19,000 total chunks** in the vector database

## License

MIT

## Resources

- [Broadband Forum GitHub](https://github.com/BroadbandForum)
- [TR-069 (CWMP)](https://www.broadband-forum.org/protocols/tr-069)
- [TR-369 (USP)](https://www.broadband-forum.org/protocols/tr-369)
- [Model Context Protocol](https://modelcontextprotocol.io/)
