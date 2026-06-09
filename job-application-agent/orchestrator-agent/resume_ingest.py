"""Layer 2 - resume file management.

Responsibilities:
* Copy a user-provided PDF/DOCX/TXT into the agent's `data/resumes/` dir.
* Extract plain text (so it can be sent to LLMs and indexed for RAG).
* Return both the canonical on-disk path and the extracted text.
"""

from __future__ import annotations

import shutil
from hashlib import sha256
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


class ResumeIngestError(Exception):
    pass


def _extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise ResumeIngestError(
                "pypdf is required to parse PDF resumes - `pip install pypdf`"
            ) from exc

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                pages.append("")
        return "\n\n".join(p.strip() for p in pages if p.strip())

    if ext == ".docx":
        try:
            import docx  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ResumeIngestError(
                "python-docx is required to parse .docx resumes - `pip install python-docx`"
            ) from exc

        document = docx.Document(str(path))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())

    # Plain text / markdown
    return path.read_text(encoding="utf-8", errors="ignore")


def ingest_resume(
    source_path: str | Path,
    user_key: str,
    data_dir: str | Path,
) -> tuple[Path, str]:
    """Copy the resume into `data_dir/resumes/<user_key><ext>` and return
    (canonical_path, extracted_text).

    Raises `ResumeIngestError` on a missing / unsupported file.
    """
    src = Path(source_path).expanduser()
    if not src.exists():
        raise ResumeIngestError(f"Source resume file not found: {src}")

    ext = src.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ResumeIngestError(
            f"Unsupported resume type {ext!r}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    dest_dir = Path(data_dir) / "resumes"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{user_key}{ext}"

    # If the source IS the destination already, don't copy on top of itself.
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    text = _extract_text(dest)
    if not text.strip():
        raise ResumeIngestError(
            f"Could not extract any text from {src}. Is the PDF scanned / image-only?"
        )

    return dest, text


def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """Split resume text into overlapping chunks suitable for embedding.

    Prefers paragraph boundaries; falls back to a sliding character window when
    paragraphs are too long. Empty / whitespace-only chunks are dropped.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""

    def flush_buf():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for p in paragraphs:
        if len(p) > chunk_size:
            flush_buf()
            # Sliding window over the long paragraph.
            i = 0
            while i < len(p):
                chunks.append(p[i : i + chunk_size].strip())
                i += chunk_size - overlap
            continue

        if len(buf) + len(p) + 2 > chunk_size:
            flush_buf()
        buf = (buf + "\n\n" + p).strip() if buf else p

    flush_buf()
    # Drop accidental dupes while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def file_fingerprint(path: Path) -> str:
    """sha256 of a file, hex-encoded. Used to detect resume changes."""
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def stats(path: Path) -> dict:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": file_fingerprint(path),
    }


def _self_test() -> None:  # pragma: no cover - manual CLI helper
    import sys

    if len(sys.argv) < 3:
        print("Usage: python resume_ingest.py <resume_path> <user_key>")
        sys.exit(2)

    data_dir = Path(__file__).resolve().parent / "data"
    dest, text = ingest_resume(sys.argv[1], sys.argv[2], data_dir)
    chunks = chunk_text(text)
    print(f"Saved to: {dest}")
    print(f"Extracted chars: {len(text)}")
    print(f"Chunks: {len(chunks)}")
    print(f"First chunk:\n{chunks[0][:300] if chunks else '(empty)'}")


if __name__ == "__main__":  # pragma: no cover
    _self_test()


_: Optional[str] = None  # avoid unused-import lint on `Optional` for older type-checkers
