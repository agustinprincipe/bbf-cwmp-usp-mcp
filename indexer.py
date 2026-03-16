"""
BBF Data Model Indexer

Indexes BBF data from data/ directory (fetched by bbf_fetcher.py):
- XML data models (CWMP + USP) via BBFXMLParser -> ChromaDB semantic chunks
- USP specification markdown -> ChromaDB semantic chunks
- Protocol schemas (XSD/proto) -> ChromaDB semantic chunks
"""
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
from sys import stderr

from xml_parser import BBFXMLParser, DataModel


DATA_DIR = Path("data")
VECTOR_DB_DIR = DATA_DIR / "vector_db"


class BBFIndexer:
    """Indexes BBF data models, specs, and protocol schemas into ChromaDB."""

    COLLECTIONS = [
        "cwmp_datamodel",
        "usp_datamodel",
        "usp_spec",
        "cwmp_protocols",
        "usp_protocols",
    ]

    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 3000,
    ):
        self.data_dir = data_dir
        self.vector_db_dir = data_dir / "vector_db"
        self.chunk_size = chunk_size

        print(f"Loading embedding model: {model_name}", file=stderr)
        self.model = SentenceTransformer(model_name)

    def _get_client(self) -> chromadb.PersistentClient:
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(self.vector_db_dir))

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks on paragraph boundaries."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        current = ""
        for para in text.split("\n\n"):
            if len(current) + len(para) + 2 > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                current = para
            else:
                current += para + "\n\n"
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _make_param_doc(self, obj_path: str, param) -> str:
        """Create a semantic document for a parameter."""
        parts = [f"Parameter: {obj_path}{param.name}"]
        parts.append(f"Type: {param.data_type}")
        parts.append(f"Access: {param.access}")
        if param.description:
            parts.append(param.description)
        if param.enumerations:
            parts.append(f"Values: {', '.join(param.enumerations)}")
        if param.range_min is not None or param.range_max is not None:
            parts.append(f"Range: [{param.range_min}, {param.range_max}]")
        return "\n".join(parts)

    def _make_obj_doc(self, obj) -> str:
        """Create a semantic document for an object."""
        parts = [f"Object: {obj.name}"]
        if obj.is_multi_instance:
            parts.append(f"Multi-instance (max: {obj.max_entries})")
        parts.append(f"Access: {obj.access}")
        if obj.description:
            parts.append(obj.description)
        param_names = list(obj.parameters.keys())
        if param_names:
            parts.append(f"Parameters: {', '.join(param_names[:20])}")
            if len(param_names) > 20:
                parts.append(f"  ... and {len(param_names) - 20} more")
        return "\n".join(parts)

    def index_data_model(self, xml_path: Path, collection_name: str) -> int:
        """Parse an XML data model and index objects+parameters into ChromaDB."""
        parser = BBFXMLParser()
        dm = parser.parse(xml_path)

        client = self._get_client()
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=collection_name)

        chunk_id = 0
        source = xml_path.name

        for obj_path, obj in dm.objects.items():
            # Index the object itself
            doc = self._make_obj_doc(obj)
            embedding = self.model.encode([doc])
            collection.add(
                embeddings=embedding,
                documents=[doc],
                metadatas=[{
                    "source": source,
                    "path": obj_path,
                    "type": "object",
                    "access": obj.access,
                    "multi_instance": str(obj.is_multi_instance),
                }],
                ids=[str(chunk_id)],
            )
            chunk_id += 1

            # Index each parameter
            for param_name, param in obj.parameters.items():
                doc = self._make_param_doc(obj_path, param)
                embedding = self.model.encode([doc])
                collection.add(
                    embeddings=embedding,
                    documents=[doc],
                    metadatas=[{
                        "source": source,
                        "path": f"{obj_path}{param_name}",
                        "type": "parameter",
                        "data_type": param.data_type,
                        "access": param.access,
                    }],
                    ids=[str(chunk_id)],
                )
                chunk_id += 1

        print(f"  {source}: {len(dm.objects)} objects, {chunk_id - len(dm.objects)} params -> {chunk_id} chunks", file=stderr)
        return chunk_id

    def index_markdown_dir(self, dir_path: Path, collection_name: str) -> int:
        """Index all markdown files in a directory into ChromaDB."""
        md_files = sorted(dir_path.rglob("*.md"))
        if not md_files:
            print(f"  No markdown files in {dir_path}", file=stderr)
            return 0

        client = self._get_client()
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=collection_name)

        chunk_id = 0
        for md_path in md_files:
            content = md_path.read_text(encoding="utf-8")
            if not content.strip():
                continue

            chunks = self._chunk_text(content)
            rel_path = md_path.relative_to(dir_path)

            for chunk_idx, chunk in enumerate(chunks):
                embedding = self.model.encode([chunk])
                collection.add(
                    embeddings=embedding,
                    documents=[chunk],
                    metadatas=[{
                        "source": str(rel_path),
                        "chunk": f"{chunk_idx + 1}/{len(chunks)}",
                    }],
                    ids=[str(chunk_id)],
                )
                chunk_id += 1

        print(f"  {len(md_files)} files -> {chunk_id} chunks", file=stderr)
        return chunk_id

    def index_schema_files(self, files: list[Path], collection_name: str) -> int:
        """Index protocol schema files (XSD, proto) into ChromaDB."""
        if not files:
            return 0

        client = self._get_client()
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=collection_name)

        chunk_id = 0
        for file_path in files:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue

            chunks = self._chunk_text(content)
            for chunk_idx, chunk in enumerate(chunks):
                embedding = self.model.encode([chunk])
                collection.add(
                    embeddings=embedding,
                    documents=[chunk],
                    metadatas=[{
                        "source": file_path.name,
                        "chunk": f"{chunk_idx + 1}/{len(chunks)}",
                    }],
                    ids=[str(chunk_id)],
                )
                chunk_id += 1

            print(f"  {file_path.name}: {len(chunks)} chunks", file=stderr)

        return chunk_id

    def run_full_indexing(self):
        """Run complete indexing pipeline."""
        print("=" * 60, file=stderr)
        print("BBF Data Indexer", file=stderr)
        print("=" * 60, file=stderr)

        cwmp_dir = self.data_dir / "cwmp"
        usp_dir = self.data_dir / "usp"
        usp_spec_dir = self.data_dir / "usp-spec"

        # 1. CWMP data models
        print("\n[CWMP Data Models]", file=stderr)
        cwmp_xmls = sorted(cwmp_dir.glob("*-full.xml")) if cwmp_dir.exists() else []
        total_cwmp = 0
        if cwmp_xmls:
            # Index the main full XMLs into one collection
            # We process each file and accumulate into the same collection
            # For simplicity, index the largest (latest) one
            for xml_path in cwmp_xmls:
                # Each XML gets its own sub-indexing but same collection approach
                # Actually, we want TR-181 CWMP and TR-098 in the same collection
                pass

            # Index all full XMLs together
            client = self._get_client()
            try:
                client.delete_collection(name="cwmp_datamodel")
            except Exception:
                pass
            collection = client.create_collection(name="cwmp_datamodel")

            chunk_id = 0
            parser = BBFXMLParser()
            for xml_path in cwmp_xmls:
                dm = parser.parse(xml_path)
                source = xml_path.name

                for obj_path, obj in dm.objects.items():
                    doc = self._make_obj_doc(obj)
                    embedding = self.model.encode([doc])
                    collection.add(
                        embeddings=embedding,
                        documents=[doc],
                        metadatas=[{
                            "source": source,
                            "path": obj_path,
                            "type": "object",
                            "access": obj.access,
                            "multi_instance": str(obj.is_multi_instance),
                        }],
                        ids=[str(chunk_id)],
                    )
                    chunk_id += 1

                    for param_name, param in obj.parameters.items():
                        doc = self._make_param_doc(obj_path, param)
                        embedding = self.model.encode([doc])
                        collection.add(
                            embeddings=embedding,
                            documents=[doc],
                            metadatas=[{
                                "source": source,
                                "path": f"{obj_path}{param_name}",
                                "type": "parameter",
                                "data_type": param.data_type,
                                "access": param.access,
                            }],
                            ids=[str(chunk_id)],
                        )
                        chunk_id += 1

                print(f"  {source}: {len(dm.objects)} objects indexed", file=stderr)

            total_cwmp = chunk_id
            print(f"  Total: {total_cwmp} chunks", file=stderr)
        else:
            print("  No CWMP XML files found", file=stderr)

        # 2. USP data model
        print("\n[USP Data Models]", file=stderr)
        usp_xmls = sorted(usp_dir.glob("*-full.xml")) if usp_dir.exists() else []
        total_usp = 0
        if usp_xmls:
            # Use index_data_model for single file, or inline for multiple
            total_usp = self.index_data_model(usp_xmls[0], "usp_datamodel")
        else:
            print("  No USP XML files found", file=stderr)

        # 3. USP specification (markdown)
        print("\n[USP Specification]", file=stderr)
        total_spec = 0
        if usp_spec_dir.exists():
            total_spec = self.index_markdown_dir(usp_spec_dir, "usp_spec")
        else:
            print("  USP spec directory not found", file=stderr)

        # 4. CWMP protocol schemas (XSD)
        print("\n[CWMP Protocol Schemas]", file=stderr)
        cwmp_xsd = sorted(cwmp_dir.glob("*.xsd")) if cwmp_dir.exists() else []
        total_cwmp_proto = self.index_schema_files(cwmp_xsd, "cwmp_protocols")
        if not cwmp_xsd:
            print("  No XSD files found", file=stderr)

        # 5. USP protocol schemas (proto)
        print("\n[USP Protocol Schemas]", file=stderr)
        usp_protos = sorted(usp_spec_dir.glob("*.proto")) if usp_spec_dir.exists() else []
        total_usp_proto = self.index_schema_files(usp_protos, "usp_protocols")
        if not usp_protos:
            print("  No proto files found", file=stderr)

        # Summary
        print(f"\n{'=' * 60}", file=stderr)
        print("Indexing Complete!", file=stderr)
        print(f"  CWMP data model: {total_cwmp} chunks", file=stderr)
        print(f"  USP data model:  {total_usp} chunks", file=stderr)
        print(f"  USP spec:        {total_spec} chunks", file=stderr)
        print(f"  CWMP protocols:  {total_cwmp_proto} chunks", file=stderr)
        print(f"  USP protocols:   {total_usp_proto} chunks", file=stderr)
        total = total_cwmp + total_usp + total_spec + total_cwmp_proto + total_usp_proto
        print(f"  TOTAL:           {total} chunks", file=stderr)
        print("=" * 60, file=stderr)
