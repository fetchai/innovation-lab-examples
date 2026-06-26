import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter


class LocalRagEngine:
    def __init__(self, persist_dir="./data/chroma"):
        """Initializes the vector database and embedding models."""
        # Ensure the data directory exists
        os.makedirs(persist_dir, exist_ok=True)

        print("[RAG Engine] Initializing ChromaDB and local embedding model...")
        # Persistent client saves data to your disk so it survives restarts
        self.client = chromadb.PersistentClient(path=persist_dir)

        # We use a lightweight, free, local embedding model from HuggingFace
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Get or create our workspace collection
        self.collection = self.client.get_or_create_collection(
            name="workspace_context", embedding_function=self.embed_fn
        )

        # Intelligent text splitter to avoid breaking sentences/code blocks in half
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=100, length_function=len
        )
        print("[RAG Engine] Initialization complete.")

    def index_file(self, file_path: str):
        """Reads a file, chunks it, and saves it to the vector database."""
        if not os.path.exists(file_path):
            print(f"[RAG Engine] Warning: File not found - {file_path}")
            return

        try:
            # Handle different encodings (Windows vs Linux) safely
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 1. Purge old chunks for this file to prevent duplicates on edit
            self.purge_file(file_path)

            if not content.strip():
                return  # Skip empty files

            # 2. Split the content into chunks
            chunks = self.splitter.split_text(content)

            documents = []
            metadatas = []
            ids = []

            # 3. Format data for ChromaDB
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({"source": file_path, "chunk_index": i})
                ids.append(f"{file_path}_chunk_{i}")

            # 4. Upsert into database
            if documents:
                self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
                print(f"[RAG Engine] Indexed: {file_path} ({len(chunks)} chunks)")

        except Exception as e:
            print(f"[RAG Engine] Error indexing {file_path}: {e}")

    def purge_file(self, file_path: str):
        """Removes a file's chunks from the database."""
        try:
            self.collection.delete(where={"source": file_path})
        except Exception:
            pass  # Fails silently if file wasn't in DB yet

    def query_context(self, query: str, top_k: int = 2) -> str:
        """Searches the database for the most relevant file chunks."""
        results = self.collection.query(query_texts=[query], n_results=top_k)

        if not results or not results["documents"] or len(results["documents"][0]) == 0:
            return "No matching workspace context found."

        # Format the retrieved chunks into a clean payload
        context_blocks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            context_blocks.append(f"--- Source: {meta['source']} ---\n{doc}")

        return "\n\n".join(context_blocks)


# ==========================================
# TEST BLOCK
# ==========================================
# This will only run if you execute this file directly (not when imported by the agent)
if __name__ == "__main__":
    # 1. Create a dummy test file
    test_file = "test_config.md"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""# Test Config
This is a simple test configuration file for demonstration purposes.
""")

    # 2. Initialize our Engine
    engine = LocalRagEngine()

    # 3. Index the file
    print("\n--- Indexing ---")
    engine.index_file(test_file)

    # 4. Query the engine
    print("\n--- Querying ---")
    test_query = "What is the purpose of the test configuration file?"
    print(f"Question: {test_query}\n")

    answer = engine.query_context(test_query)
    print(f"Retrieved Context:\n{answer}")

    # Clean up the dummy file
    if os.path.exists(test_file):
        os.remove(test_file)
