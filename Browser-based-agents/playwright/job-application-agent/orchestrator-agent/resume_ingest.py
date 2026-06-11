"""Resume file management — copy, extract plain text, return path + text."""

from __future__ import annotations

import shutil
from pathlib import Path

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
    # Keep the source filename so the original name (not the user_key / agent
    # address) is what gets submitted to job applications.
    dest = dest_dir / src.name

    # If the source IS the destination already, don't copy on top of itself.
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)

    text = _extract_text(dest)
    if not text.strip():
        raise ResumeIngestError(
            f"Could not extract any text from {src}. Is the PDF scanned / image-only?"
        )

    return dest, text


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 3:
        print("Usage: python resume_ingest.py <resume_path> <user_key>")
        sys.exit(2)
    dest, text = ingest_resume(sys.argv[1], sys.argv[2], Path(__file__).resolve().parent / "data")
    print(f"Saved to: {dest}\nExtracted chars: {len(text)}")
