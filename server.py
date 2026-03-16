"""
Unified TR-069 (CWMP) and TR-369 (USP) MCP Server

Provides tools for searching:
- TR-069 and TR-369 standard specifications
- Data models (TR-098 for TR-069, TR-181 shared)
- Protocol definitions (CWMP XSD/XML for TR-069, protobuf for TR-369)
"""
import asyncio
from pathlib import Path
from sys import stderr
from typing import Any, Sequence

import chromadb
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sentence_transformers import SentenceTransformer

# Initialize
DATA_DIR = Path(__file__).parent / "data"

app = Server("tr-mcp-server")

# Global state for vector stores
chroma_clients = {}
collections = {}
model = None


def init_vector_store():
    """Initialize ChromaDB clients and embedding model for all protocols."""
    global chroma_clients, collections, model

    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded", file=stderr)
    except Exception as e:
        print(f"⚠️  Failed to load embedding model: {e}", file=stderr)
        return

    # Initialize TR-069 collections
    try:
        tr069_client = chromadb.PersistentClient(path=str(DATA_DIR / "tr069/vector_db"))
        chroma_clients["tr069"] = tr069_client

        collections["tr069_standards"] = tr069_client.get_collection("tr069_standards")
        collections["tr069_data_models"] = tr069_client.get_collection("tr069_data_models")
        collections["tr069_protocols"] = tr069_client.get_collection("tr069_protocols")
        print("✅ TR-069 (CWMP) collections loaded", file=stderr)
    except Exception as e:
        print(f"⚠️  TR-069 collections not found: {e}", file=stderr)
        print("   Please run: python indexer.py --protocols tr069", file=stderr)

    # Initialize TR-369 collections
    try:
        tr369_client = chromadb.PersistentClient(path=str(DATA_DIR / "tr369/vector_db"))
        chroma_clients["tr369"] = tr369_client

        collections["tr369_standards"] = tr369_client.get_collection("tr369_standards")
        collections["tr369_protocols"] = tr369_client.get_collection("tr369_protocols")
        print("✅ TR-369 (USP) collections loaded", file=stderr)
    except Exception as e:
        print(f"⚠️  TR-369 collections not found: {e}", file=stderr)
        print("   Please run: python indexer.py --protocols tr369", file=stderr)

    # Initialize shared collections (TR-181)
    try:
        shared_client = chromadb.PersistentClient(path=str(DATA_DIR / "shared/vector_db"))
        chroma_clients["shared"] = shared_client

        collections["shared_data_models"] = shared_client.get_collection("shared_data_models")
        print("✅ Shared data models (TR-181) loaded", file=stderr)
    except Exception as e:
        print(f"⚠️  Shared data models not found: {e}", file=stderr)
        print("   Please run: python indexer.py --protocols shared", file=stderr)

    if not collections:
        print("⚠️  No collections loaded. Please run indexer.py first.", file=stderr)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        # TR-069 (CWMP) Tools
        Tool(
            name="search_tr069_standard",
            description=(
                "Search TR-069 (CWMP) standard specification documents. "
                "Returns relevant sections from the TR-069 protocol specification. "
                "Use for: understanding CWMP protocol details, RPC methods, "
                "session management, fault codes, authentication mechanisms."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for TR-069 standard. Examples: "
                            "'GetParameterValues RPC', 'CWMP session establishment', "
                            "'fault code 9005', 'HTTP authentication'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_tr069_data_models",
            description=(
                "Search TR-069 data models (TR-098 and related). "
                "Returns relevant data model object definitions and parameters. "
                "Use for: finding device parameters, understanding object hierarchies, "
                "parameter access types, data types, and parameter descriptions. "
                "Examples: Device.WiFi, InternetGatewayDevice, parameter constraints."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for TR-098 data models. Examples: "
                            "'Device.WiFi.SSID', 'InternetGatewayDevice.WANDevice', "
                            "'SSID parameters', 'WiFi radio configuration'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_tr069_protocols",
            description=(
                "Search TR-069 CWMP protocol definitions (XSD/XML schemas). "
                "Returns SOAP/XML schema definitions for CWMP messages and structures. "
                "Use for: understanding CWMP message formats, RPC structures, "
                "parameter structures, fault definitions, XML namespaces, "
                "and SOAP envelope formats. Examples: cwmp:Inform, "
                "ParameterValueStruct, SetParameterValuesResponse schema."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for CWMP XSD/XML. Examples: "
                            "'cwmp:Inform', 'ParameterValueStruct', "
                            "'SetParameterValues schema', 'Fault structure'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),

        # TR-369 (USP) Tools
        Tool(
            name="search_tr369_standard",
            description=(
                "Search TR-369 (USP) standard specification documents. "
                "Returns relevant sections from the USP protocol specification. "
                "Use for: understanding USP protocol details, message types, "
                "MTP (Message Transfer Protocols), E2E security, discovery, "
                "subscription mechanisms, USP Record/Message structure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for TR-369 standard. Examples: "
                            "'USP Get message', 'STOMP MTP', 'E2E session context', "
                            "'subscription notifications', 'USP Record encoding'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_tr369_protocols",
            description=(
                "Search TR-369 USP protocol definitions (protobuf schemas). "
                "Returns protobuf message definitions for USP. "
                "Use for: understanding USP message structures, field definitions, "
                "message encoding, Request/Response structures, Error definitions, "
                "and protobuf message types. Examples: Get, Set, Add, Delete, "
                "Operate requests, Notify messages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for USP protobuf definitions. Examples: "
                            "'Get message proto', 'Set request structure', "
                            "'Notify message', 'Error proto definition'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),

        # Shared Tools
        Tool(
            name="search_shared_data_models",
            description=(
                "Search shared data models (TR-181 Device:2). "
                "TR-181 is the unified data model used by both TR-069 and TR-369. "
                "Returns data model object definitions, parameters, events, and commands. "
                "Use for: finding device parameters, understanding object hierarchies, "
                "multi-instance objects, parameter types, and USP commands/events. "
                "Examples: Device.WiFi, Device.Ethernet, Device.LocalAgent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query for TR-181 data models. Examples: "
                            "'Device.WiFi.Radio', 'Device.LocalAgent.Controller', "
                            "'WiFi AccessPoint parameters', 'Device.IP.Interface'"
                        )
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
    ]


def truncate_output(text: str, max_tokens: int = 20000) -> str:
    """
    Truncate output to avoid exceeding token limits.
    Rough estimate: 1 token ≈ 4 characters
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    return truncated + f"\n\n[... Output truncated. Total: {len(text)} chars, showing first {max_chars} ...]"


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls."""
    if model is None:
        return [TextContent(
            type="text",
            text="⚠️ Embedding model not initialized. Please check server logs."
        )]

    query = arguments["query"]
    top_k = arguments.get("top_k", 5)

    # Map tool names to collection names
    tool_to_collection = {
        "search_tr069_standard": "tr069_standards",
        "search_tr069_data_models": "tr069_data_models",
        "search_tr069_protocols": "tr069_protocols",
        "search_tr369_standard": "tr369_standards",
        "search_tr369_protocols": "tr369_protocols",
        "search_shared_data_models": "shared_data_models",
    }

    collection_name = tool_to_collection.get(name)
    if not collection_name:
        raise ValueError(f"Unknown tool: {name}")

    collection = collections.get(collection_name)
    if collection is None:
        protocol = "TR-069" if "tr069" in name else "TR-369" if "tr369" in name else "Shared"
        return [TextContent(
            type="text",
            text=f"⚠️ {protocol} collection '{collection_name}' not initialized.\n"
                 f"Please run: python indexer.py"
        )]

    # Generate query embedding
    query_embedding = model.encode(query).tolist()

    # Search collection
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"]
        )
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"⚠️ Error searching collection: {e}"
        )]

    # Format output
    protocol_name = {
        "tr069_standards": "TR-069 (CWMP) Standard",
        "tr069_data_models": "TR-069 Data Models (TR-098)",
        "tr069_protocols": "TR-069 CWMP Protocols (XSD/XML)",
        "tr369_standards": "TR-369 (USP) Standard",
        "tr369_protocols": "TR-369 USP Protocols (Protobuf)",
        "shared_data_models": "Shared Data Models (TR-181)",
    }[collection_name]

    output = f"# Search Results: '{query}'\n"
    output += f"**Source:** {protocol_name}\n"
    output += f"**Results:** {len(results['documents'][0])}\n\n"
    output += "---\n\n"

    if not results['documents'][0]:
        output += "No results found.\n"
    else:
        for i, doc in enumerate(results['documents'][0]):
            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
            distance = results['distances'][0][i] if results.get('distances') else None

            # Add metadata info if available
            if metadata:
                source = metadata.get('source', 'Unknown')
                source_path = Path(source)
                output += f"**[Result {i+1}]** {source_path.name}\n"

                if 'chunk' in metadata:
                    output += f"*Chunk: {metadata['chunk']}*\n\n"
                else:
                    output += "\n"

            # Add relevance score
            if distance is not None:
                output += f"*Relevance: {1 - distance:.2%}*\n\n"

            # Add document content
            output += f"{doc}\n\n"
            output += "---\n\n"

    # Truncate if needed
    output = truncate_output(output)
    return [TextContent(type="text", text=output)]


async def main():
    """Run the MCP server."""
    print("=" * 80, file=stderr)
    print("TR-069 (CWMP) & TR-369 (USP) MCP Server", file=stderr)
    print("=" * 80, file=stderr)

    init_vector_store()

    print("\n🚀 Server ready", file=stderr)
    print("=" * 80, file=stderr)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
