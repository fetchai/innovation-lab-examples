"""
Document ingestion utility.

Run this script to pre-load a document into the ChromaDB vector store
before starting the agent.
"""

from __future__ import annotations

import sys

from rag import index_document


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <path-to-document>")
        print("Supported formats: .pdf, .txt, .md, .csv")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Ingesting document: {path}")

    try:
        chunk_count = index_document(path)
        print(f"Successfully ingested {chunk_count} chunks into ChromaDB.")
        print("You can now start the agent and ask questions.")
    except FileNotFoundError:
        print(f"Error: File not found: {path}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
