"""
Unified TR-069 (CWMP) and TR-369 (USP) Documentation Indexer

Handles PDF conversion and vector database indexing for:
- TR-069 standard documents and CWMP protocols (XSD/XML)
- TR-369 standard documents and USP protocols (protobuf)
- Shared data models (TR-181)
- Protocol-specific data models (TR-098 for TR-069)
"""
import chromadb
from sentence_transformers import SentenceTransformer
from docling.document_converter import DocumentConverter
from pathlib import Path
import glob
from typing import Literal, Optional


class UnifiedTRIndexer:
    """Unified indexer for TR-069 and TR-369 documentation."""

    def __init__(
        self,
        data_dir: str = "data",
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 5000
    ):
        """
        Initialize the unified indexer.

        Args:
            data_dir: Root directory containing tr069/, tr369/, and shared/ subdirectories
            model_name: Sentence transformer model for embeddings
            chunk_size: Maximum characters per chunk for protocol files
        """
        self.data_dir = Path(data_dir)
        self.chunk_size = chunk_size

        # Directory structure
        self.tr069_dir = self.data_dir / "tr069"
        self.tr369_dir = self.data_dir / "tr369"
        self.shared_dir = self.data_dir / "shared"

        # Initialize embedding model
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        # Collections will be stored separately
        self.collections = {}

    def _get_chroma_client(self, protocol: Literal["tr069", "tr369", "shared"]) -> chromadb.PersistentClient:
        """Get ChromaDB client for specific protocol."""
        vector_db_path = self.data_dir / protocol / "vector_db"
        vector_db_path.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(vector_db_path))

    def _chunk_text(self, text: str, max_chars: int) -> list[str]:
        """
        Split text into chunks of approximately max_chars size.
        Tries to split on paragraph boundaries when possible.
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    # Single paragraph is too large, split by sentences
                    sentences = para.split(". ")
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 2 > max_chars:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + ". "
                        else:
                            current_chunk += sentence + ". "
            else:
                current_chunk += para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def convert_pdfs_to_markdown(
        self,
        protocol: Literal["tr069", "tr369", "shared"],
        doc_type: Literal["standards", "data_models"],
        force: bool = False
    ):
        """Convert PDFs to markdown format."""
        base_dir = self.data_dir / protocol
        pdf_dir = base_dir / doc_type
        markdown_dir = base_dir / "markdown" / doc_type

        if not pdf_dir.exists():
            print(f"Directory not found: {pdf_dir}")
            return

        markdown_dir.mkdir(parents=True, exist_ok=True)
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            print(f"No PDF files found in {pdf_dir}")
            return

        print(f"\nConverting {len(pdf_files)} PDFs from {pdf_dir}...")
        converter = DocumentConverter()

        for pdf_path in pdf_files:
            markdown_path = markdown_dir / f"{pdf_path.stem}.md"

            if markdown_path.exists() and not force:
                print(f"  ✓ {pdf_path.name} (already converted)")
                continue

            try:
                print(f"  Converting {pdf_path.name}...")
                result = converter.convert(str(pdf_path))
                markdown_content = result.document.export_to_markdown()

                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                print(f"  ✓ {pdf_path.name} -> {markdown_path.name}")
            except Exception as e:
                print(f"  ✗ Error converting {pdf_path.name}: {e}")

    def index_markdown_files(
        self,
        protocol: Literal["tr069", "tr369", "shared"],
        doc_type: Literal["standards", "data_models"],
        collection_name: str
    ):
        """Index markdown files into ChromaDB collection."""
        base_dir = self.data_dir / protocol
        markdown_dir = base_dir / "markdown" / doc_type

        if not markdown_dir.exists():
            print(f"Markdown directory not found: {markdown_dir}")
            return

        markdown_files = list(markdown_dir.glob("*.md"))
        if not markdown_files:
            print(f"No markdown files found in {markdown_dir}")
            return

        print(f"\nIndexing {len(markdown_files)} markdown files into '{collection_name}'...")

        # Get or create collection
        client = self._get_chroma_client(protocol)
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=collection_name)

        chunk_id = 0
        for md_path in markdown_files:
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    continue

                # Split into chunks by double newline (paragraphs)
                chunks = content.split("\n\n")
                chunks = [c.strip() for c in chunks if c.strip()]

                print(f"  {md_path.name}: {len(chunks)} chunks")

                for chunk in chunks:
                    embedding = self.model.encode([chunk])
                    collection.add(
                        embeddings=embedding,
                        documents=[chunk],
                        metadatas=[{
                            "source": str(md_path),
                            "doc_type": doc_type,
                            "protocol": protocol
                        }],
                        ids=[str(chunk_id)]
                    )
                    chunk_id += 1

            except Exception as e:
                print(f"  ✗ Error indexing {md_path.name}: {e}")

        print(f"  ✓ Indexed {chunk_id} chunks total")

    def index_protocol_files(
        self,
        protocol: Literal["tr069", "tr369"],
        collection_name: str
    ):
        """
        Index protocol files (XSD/XML for TR-069, .proto for TR-369).
        """
        base_dir = self.data_dir / protocol
        protocol_dir = base_dir / "protocols"

        if not protocol_dir.exists():
            print(f"Protocol directory not found: {protocol_dir}")
            return

        # Determine file extensions based on protocol
        if protocol == "tr069":
            file_patterns = ["**/*.xml", "**/*.xsd", "**/*.xls"]
            file_desc = "CWMP XSD/XML files"
        else:  # tr369
            file_patterns = ["**/*.proto"]
            file_desc = "USP protobuf files"

        # Collect all matching files
        files_to_index = []
        for pattern in file_patterns:
            files_to_index.extend(glob.glob(str(protocol_dir / pattern), recursive=True))

        if not files_to_index:
            print(f"No {file_desc} found in {protocol_dir}")
            return

        print(f"\nIndexing {len(files_to_index)} {file_desc} into '{collection_name}'...")

        # Get or create collection
        client = self._get_chroma_client(protocol)
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(name=collection_name)

        chunk_id = 0
        for file_path in files_to_index:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if not content.strip():
                    continue

                # Chunk large files
                chunks = self._chunk_text(content, self.chunk_size)

                for chunk_idx, chunk in enumerate(chunks):
                    embedding = self.model.encode([chunk])
                    collection.add(
                        embeddings=embedding,
                        documents=[chunk],
                        metadatas=[{
                            "source": file_path,
                            "chunk": f"{chunk_idx + 1}/{len(chunks)}",
                            "protocol": protocol
                        }],
                        ids=[str(chunk_id)]
                    )
                    chunk_id += 1

                if len(chunks) > 1:
                    print(f"  {Path(file_path).name}: {len(chunks)} chunks")
                else:
                    print(f"  {Path(file_path).name}")

            except Exception as e:
                print(f"  ✗ Error indexing {file_path}: {e}")

        print(f"  ✓ Indexed {chunk_id} chunks total")

    def run_full_indexing(
        self,
        convert_pdfs: bool = True,
        force_conversion: bool = False,
        protocols: Optional[list[str]] = None
    ):
        """
        Run complete indexing pipeline for all protocols.

        Args:
            convert_pdfs: Whether to convert PDFs to markdown
            force_conversion: Force reconversion even if markdown exists
            protocols: List of protocols to index (default: all)
        """
        if protocols is None:
            protocols = ["tr069", "tr369", "shared"]

        print("=" * 80)
        print("TR-069 (CWMP) & TR-369 (USP) Unified Indexer")
        print("=" * 80)

        # TR-069 (CWMP)
        if "tr069" in protocols:
            print("\n" + "=" * 80)
            print("TR-069 (CWMP) Processing")
            print("=" * 80)

            if convert_pdfs:
                self.convert_pdfs_to_markdown("tr069", "standards", force_conversion)
                self.convert_pdfs_to_markdown("tr069", "data_models", force_conversion)

            self.index_markdown_files("tr069", "standards", "tr069_standards")
            self.index_markdown_files("tr069", "data_models", "tr069_data_models")
            self.index_protocol_files("tr069", "tr069_protocols")

        # TR-369 (USP)
        if "tr369" in protocols:
            print("\n" + "=" * 80)
            print("TR-369 (USP) Processing")
            print("=" * 80)

            if convert_pdfs:
                self.convert_pdfs_to_markdown("tr369", "standards", force_conversion)

            self.index_markdown_files("tr369", "standards", "tr369_standards")
            self.index_protocol_files("tr369", "tr369_protocols")

        # Shared (TR-181)
        if "shared" in protocols:
            print("\n" + "=" * 80)
            print("Shared Data Models (TR-181) Processing")
            print("=" * 80)

            if convert_pdfs:
                self.convert_pdfs_to_markdown("shared", "data_models", force_conversion)

            self.index_markdown_files("shared", "data_models", "shared_data_models")

        print("\n" + "=" * 80)
        print("Indexing Complete!")
        print("=" * 80)


def main():
    """Main entry point for the indexer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Index TR-069 and TR-369 documentation"
    )
    parser.add_argument(
        "--protocols",
        nargs="+",
        choices=["tr069", "tr369", "shared"],
        default=["tr069", "tr369", "shared"],
        help="Which protocols to index (default: all)"
    )
    parser.add_argument(
        "--skip-pdf-conversion",
        action="store_true",
        help="Skip PDF to markdown conversion"
    )
    parser.add_argument(
        "--force-conversion",
        action="store_true",
        help="Force reconversion of PDFs even if markdown exists"
    )

    args = parser.parse_args()

    indexer = UnifiedTRIndexer()
    indexer.run_full_indexing(
        convert_pdfs=not args.skip_pdf_conversion,
        force_conversion=args.force_conversion,
        protocols=args.protocols
    )


if __name__ == "__main__":
    main()
