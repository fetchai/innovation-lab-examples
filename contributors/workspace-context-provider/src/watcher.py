import os
import sys
import time

# Add the root directory to the python path so direct execution works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.rag_pipeline import LocalRagEngine


class WorkspaceHandler(FileSystemEventHandler):
    def __init__(self, rag_engine: LocalRagEngine, target_dir: str):
        self.rag_engine = rag_engine
        self.target_dir = target_dir
        # Only parse common readable code and documentation files
        self.valid_extensions = (
            ".py",
            ".md",
            ".js",
            ".ts",
            ".json",
            ".txt",
            ".java",
            ".cpp",
        )
        # Dictionary to track when files were last processed to avoid double-triggers
        self.last_processed = {}

    def should_process(self, path: str) -> bool:
        """Check if the file is a valid type and NOT in a hidden folder like .git"""
        # Normalize the path to fix mixed Windows/Linux slashes
        clean_path = os.path.normpath(path)

        # Check if any folder or file is hidden (starts with a dot, but isn't current/parent dir)
        if any(
            part.startswith(".") and part not in (".", "..")
            for part in clean_path.split(os.sep)
        ):
            return False

        return clean_path.endswith(self.valid_extensions)

    def debounce(self, file_path: str, wait_time: float = 1.0) -> bool:
        """Prevents multiple triggers for a single IDE save action."""
        current_time = time.time()
        if file_path in self.last_processed:
            if current_time - self.last_processed[file_path] < wait_time:
                return False  # Too soon, ignore this trigger
        self.last_processed[file_path] = current_time
        return True

    def on_modified(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            if self.debounce(event.src_path):
                time.sleep(0.2)  # Small buffer to let the OS release the file lock
                self.rag_engine.index_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            if self.debounce(event.src_path):
                time.sleep(0.2)
                self.rag_engine.index_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and self.should_process(event.src_path):
            self.rag_engine.purge_file(event.src_path)
            print(f"[Watcher] File deleted. Purged from DB: {event.src_path}")


def start_directory_watcher(rag_engine: LocalRagEngine, target_dir: str) -> Observer:
    """Bootstraps the directory and starts the background observer thread."""
    os.makedirs(target_dir, exist_ok=True)

    # 1. Run an initial bootstrap scan of existing files
    print(f"\n[Watcher] Bootstrapping directory: {target_dir}")
    handler = WorkspaceHandler(rag_engine, target_dir)

    for root, _, files in os.walk(target_dir):
        for file in files:
            full_path = os.path.join(root, file)
            if handler.should_process(full_path):
                rag_engine.index_file(full_path)

    # 2. Start listening for live changes
    observer = Observer()
    observer.schedule(handler, path=target_dir, recursive=True)
    observer.start()
    print(f"[Watcher] Actively tracking architectural changes in: {target_dir}\n")
    return observer


# ==========================================
# TEST BLOCK
# ==========================================
if __name__ == "__main__":
    # Test the watcher independently
    test_dir = "./target_workspace"
    engine = LocalRagEngine()

    # Start the background thread
    observer = start_directory_watcher(engine, test_dir)

    print("Watcher is running! Try doing this:")
    print(f"1. Open the '{test_dir}' folder.")
    print("2. Create a new file (e.g., test.md) and type something.")
    print("3. Save it and watch this terminal.")
    print("Press CTRL+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[Watcher] Stopped.")
    observer.join()
