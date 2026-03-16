"""
Main entry point for the TR-069/TR-369 MCP server.
Supports subcommands: serve (default) and init (fetch BBF data).
"""

import argparse
import asyncio
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


async def run_init(github_token: str | None = None) -> None:
    """Fetch BBF data model files from GitHub."""
    from bbf_fetcher import BBFDataFetcher

    fetcher = BBFDataFetcher(github_token=github_token)
    print(f"Fetching BBF data to {DATA_DIR}...")
    result = await fetcher.run_init(DATA_DIR)

    print(f"\nDone. {result.total_files} files downloaded.")
    for repo_name, info in result.repos.items():
        print(f"  {repo_name}: {info['files_downloaded']} files (tree: {info['tree_sha'][:7]})")
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  - {err}")
        sys.exit(1)


def run_index() -> None:
    """Index fetched BBF data into ChromaDB."""
    from indexer import BBFIndexer

    if not DATA_DIR.exists():
        print("No data directory found. Run 'python main.py init' first.")
        sys.exit(1)

    indexer = BBFIndexer(data_dir=DATA_DIR)
    indexer.run_full_indexing()


async def run_serve() -> None:
    """Start the MCP server."""
    from server import main as server_main

    await server_main()


def cli() -> None:
    parser = argparse.ArgumentParser(description="TR-069/TR-369 MCP Server")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Fetch BBF data from GitHub")
    init_parser.add_argument(
        "--token", help="GitHub personal access token (optional, increases rate limit)"
    )

    # index command
    subparsers.add_parser("index", help="Index fetched BBF data into vector DB")

    # serve command (default)
    subparsers.add_parser("serve", help="Start the MCP server (default)")

    args = parser.parse_args()

    if args.command == "init":
        asyncio.run(run_init(github_token=args.token))
    elif args.command == "index":
        run_index()
    else:
        # Default to serve
        asyncio.run(run_serve())


if __name__ == "__main__":
    cli()
