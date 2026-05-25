import os
import shutil
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def ingest_document(file_path, storage_path="./chroma_db"):
    """
    Loads a PDF or text document, chunks it, embeds it using HuggingFace models,
    and stores it in ChromaDB.
    """
    if not os.path.exists(file_path):
        print(f"Error: Document not found at {file_path}")
        return None

    print(f"Loading document: {file_path}")

    # Clear existing DB to avoid mixing contexts in this example
    if os.path.exists(storage_path):
        shutil.rmtree(storage_path)

    # Load document based on extension
    if file_path.lower().endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path)

    documents = loader.load()

    # Split documents into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(documents)

    # Initialize embeddings using a lightweight HuggingFace model
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Store in ChromaDB
    vectorstore = Chroma.from_documents(
        documents=docs, embedding=embeddings, persist_directory=storage_path
    )

    print(
        f"Successfully ingested {len(docs)} chunks from {file_path} into {storage_path}"
    )
    return vectorstore


if __name__ == "__main__":
    # Get document path from environment variable or default
    document_path = os.getenv("DOCUMENT_PATH", "sample.pdf")

    # If the default sample.pdf doesn't exist, provide a fallback message
    if not os.path.exists(document_path):
        print(f"Sample document '{document_path}' not found.")
        print(
            "Please place a PDF or .txt file in this directory or set DOCUMENT_PATH in .env"
        )
    else:
        ingest_document(document_path)
