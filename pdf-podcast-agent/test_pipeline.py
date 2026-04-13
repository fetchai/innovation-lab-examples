"""
test_pipeline.py – Local smoke test
=====================================
Calls the Orchestrator's REST endpoint with a PDF path and saves the
resulting MP3 to disk.

Usage:
    python test_pipeline.py path/to/your/document.pdf

The script will print the episode title, the full script, and save the
audio to ./output/
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import requests  # type: ignore[import-untyped]

ORCHESTRATOR_URL = "http://localhost:8000/process"


def run_test(pdf_path: str) -> None:
    path = Path(pdf_path).resolve()
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    print(f"\n📄  PDF: {path}")
    print(f"🌐  Sending to: {ORCHESTRATOR_URL}")
    print("⏳  Running pipeline (30–120 s) …\n")

    start = time.time()

    try:
        resp = requests.post(
            ORCHESTRATOR_URL,
            json={"pdf_path": str(path)},
            timeout=180,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("[ERROR] Could not reach the Orchestrator. Is `python run.py` running?")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out after 180 s.")
        sys.exit(1)

    data = resp.json()
    elapsed = time.time() - start

    if data.get("status") != "success":
        print(f"[ERROR] Pipeline failed: {data.get('error_message', 'unknown')}")
        sys.exit(1)

    # ── Print results ─────────────────────────────────────────────────────────
    title = data.get("topic_title", "Untitled")
    script = json.loads(data.get("script_json", "[]"))
    audio_path = data.get("audio_path", "")

    print(f"✅  Done in {elapsed:.1f}s\n")
    print(f"🎙️  Episode: {title}")
    print(f"📝  Script ({len(script)} lines):")
    print("-" * 50)
    for line in script:
        label = "  [A]" if line["speaker"] == "HostA" else "  [B]"
        print(f"{label}  {line['text']}")
    print("-" * 50)

    # ── Save audio ────────────────────────────────────────────────────────────
    if data.get("audio_base64"):
        audio_bytes = base64.b64decode(data["audio_base64"])
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        out_path = (
            out_dir / Path(audio_path).name if audio_path else out_dir / "podcast.mp3"
        )
        with open(out_path, "wb") as f:
            f.write(audio_bytes)
        print(f"\n🎵  Audio saved → {out_path.resolve()}")
        print(f"     Size: {len(audio_bytes) / 1024:.1f} KB")
    else:
        print("\n⚠️   No audio in response (check Voice Studio logs).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF-to-Podcast local smoke test")
    parser.add_argument("pdf", help="Path to the PDF file to process")
    args = parser.parse_args()
    run_test(args.pdf)
