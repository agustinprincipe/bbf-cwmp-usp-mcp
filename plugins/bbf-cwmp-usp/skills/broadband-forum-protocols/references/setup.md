# Setup Guide

## First-time setup (required once)

After installing the plugin, you need to fetch and index the BBF data:

```bash
cd <plugin-root>   # where the plugin was installed
uv sync             # install Python dependencies
uv run python main.py init    # fetch BBF data from GitHub (~12MB)
uv run python main.py index   # index into vector DB (~5 min)
```

## What happens during init

The `init` command downloads official BBF data model files from GitHub:
- **CWMP data models**: TR-181 Device:2 (CWMP variant) + TR-098 InternetGatewayDevice
- **USP data model**: TR-181 Device:2 (USP variant)
- **USP specification**: TR-369 spec markdown files
- **Protocol schemas**: CWMP XSD + USP protobuf definitions

Total download: ~12MB (vs ~209MB if cloning full repos).

## What happens during index

The `index` command parses XML data models and generates embeddings for semantic search:
- Parses ~1900 objects and ~15000 parameters from XML
- Creates ChromaDB vector database with ~19000 chunks
- Takes ~5 minutes (embedding computation)

## Updating data

To get the latest BBF data models (when new versions are published):

```bash
uv run python main.py init    # re-fetches latest from GitHub
uv run python main.py index   # re-indexes
```

## Requirements

- Python 3.13+
- uv (Python package manager)
- Internet connection (for init only)
