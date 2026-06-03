"""Layer 3 - Qdrant + FastEmbed RAG over the user's resume.

Uses Qdrant in *local persistent* mode (no server / docker needed) and
FastEmbed for embeddings (small ONNX model bundled by `qdrant-client[fastembed]`,
default: BAAI/bge-small-en-v1.5).

Collections are keyed per user so multiple users can coexist in a single
on-disk store:  collection name = `f"resume_{user_key}"`.

The store is intentionally optional - all callers degrade gracefully if Qdrant
isn't importable or no resume has been indexed yet.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


class ResumeRAGUnavailable(RuntimeError):
    """Raised on operations that need the optional qdrant-client[fastembed] extra."""


def _safe_collection_name(user_key: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", user_key).strip("_") or "default"
    return f"resume_{safe}"


class ResumeRAG:
    """Per-user resume vector index.

    Pass a `data_dir` and the Qdrant store will live at `data_dir/qdrant/`.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.qdrant_path = self.data_dir / "qdrant"
        self.qdrant_path.mkdir(parents=True, exist_ok=True)
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ResumeRAGUnavailable(
                "qdrant-client is not installed. Install with "
                "`pip install 'qdrant-client[fastembed]'`."
            ) from exc

        self._client = QdrantClient(path=str(self.qdrant_path))
        return self._client

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def index(self, user_key: str, chunks: list[str]) -> int:
        """(Re)index a user's resume chunks. Returns the number indexed.

        Drops any prior collection for this user so re-uploading a resume
        gives clean results (no stale chunks from the old version).
        """
        if not chunks:
            return 0

        client = self._ensure_client()
        collection = _safe_collection_name(user_key)

        # Wipe prior data for this user.
        try:
            client.delete_collection(collection_name=collection)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass

        ids = list(range(len(chunks)))
        metadata = [{"chunk_index": i} for i in ids]
        # client.add() lazily embeds via FastEmbed and creates the collection.
        client.add(
            collection_name=collection,
            documents=chunks,
            metadata=metadata,
            ids=ids,
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def search(self, user_key: str, query: str, k: int = 4) -> list[str]:
        """Return up to `k` resume chunks most relevant to `query`.

        Returns an empty list if the user has no indexed resume or if Qdrant
        is unavailable. Never raises - this is a best-effort enrichment.
        """
        if not query.strip():
            return []
        try:
            client = self._ensure_client()
        except ResumeRAGUnavailable:
            return []

        collection = _safe_collection_name(user_key)
        try:
            results = client.query(collection_name=collection, query_text=query, limit=k)
        except Exception:  # noqa: BLE001 - missing collection / empty index
            return []

        # qdrant-client returns QueryResponse objects with `.document` and `.metadata`.
        out: list[str] = []
        for r in results or []:
            doc = getattr(r, "document", None) or (r.metadata or {}).get("document")
            if doc:
                out.append(doc)
        return out

    def has_index(self, user_key: str) -> bool:
        try:
            client = self._ensure_client()
        except ResumeRAGUnavailable:
            return False
        try:
            return client.collection_exists(_safe_collection_name(user_key))
        except Exception:  # noqa: BLE001
            return False


def _self_test() -> None:  # pragma: no cover - manual CLI helper
    import sys

    if len(sys.argv) < 3:
        print("Usage: python rag.py <user_key> <query>")
        sys.exit(2)

    data_dir = Path(__file__).resolve().parent / "data"
    rag = ResumeRAG(data_dir)
    hits = rag.search(sys.argv[1], sys.argv[2], k=5)
    if not hits:
        print("No results (no index for this user yet?)")
        return
    for i, h in enumerate(hits, 1):
        print(f"--- hit {i} ---\n{h[:400]}\n")


if __name__ == "__main__":  # pragma: no cover
    _self_test()


_: Optional[str] = None  # quiet unused-import on Optional in some linters
