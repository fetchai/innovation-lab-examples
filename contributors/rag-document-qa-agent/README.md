# RAG Document QA Agent

A Retrieval-Augmented Generation (RAG) agent that allows you to chat with your PDF or plain-text documents. It uses HuggingFace embeddings, ChromaDB for vector storage, and Gemini 2.0 Flash as the LLM backbone, all integrated within the uAgents framework.

- **Category:** `RAG`, `LLM`, `Integration`
- **Difficulty:** Intermediate
- **Tech stack:** `uAgents`, `LangChain`, `ChromaDB`, `Gemini 2.0 Flash`, `HuggingFace`
- **Status:** Prototype

## 2) Overview

This agent demonstrates how to build a document-grounded Q&A system inside the uAgents ecosystem. Most RAG systems are built as simple scripts, but this example shows how to wrap that logic into an autonomous agent that can communicate via the uAgents chat protocol.

It's useful for researchers, students, or anyone who wants a private, agentic way to query their local documents.

## 3) Features

- **Multi-format Support:** Accepts both PDF and TXT files.
- **Local Embeddings:** Uses HuggingFace `sentence-transformers` for efficient local embedding generation.
- **Vector Search:** Powered by ChromaDB for fast and accurate context retrieval.
- **Agentic Interface:** Responds to natural language questions via the uAgents communication protocol.
- **Zero Cost:** Uses the Gemini 2.0 Flash free tier.

## 4) Prerequisites

- Python 3.10 or higher
- [Google AI Studio API Key](https://aistudio.google.com/app/apikey) (Free)
- Agentverse API Key (Optional, for registration)

## 5) Installation

```bash
# Clone the repository
git clone https://github.com/fetchai/innovation-lab-examples.git
cd contributors/rag-document-qa-agent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 6) Environment Variables

Create a `.env` file using the provided `.env.example`:

```bash
cp .env.example .env
```

### Variables

- `GOOGLE_API_KEY`: Your Gemini 2.0 Flash API key.
- `AGENTVERSE_API_KEY` (Optional): Required for registering the agent on Agentverse.
- `DOCUMENT_PATH`: The relative path to the PDF or text file you want to query (default: `./sample.pdf`).

## 7) Run the Agent

### Step 1: Ingest the Document

First, you need to process your document and create the vector database.

```bash
python ingest.py
```

### Step 2: Start the Agent

Once the database is created, run the agent.

```bash
python agent.py
```

## 8) Expected Output

### Ingestion

```text
Loading document: ./sample.pdf
Successfully ingested 15 chunks from ./sample.pdf into ./chroma_db
```

### Agent Startup

```text
INFO:  [rag_doc_agent]: RAG Agent started at agent1q...
INFO:  [rag_doc_agent]: RAG Chain initialized and ready.
```

## 9) Demo

![RAG Agent Demo](./assets/demo.png)

## 10) Architecture

1. **Ingestion Phase (`ingest.py`):**
    - Document is loaded using `PyPDFLoader` or `TextLoader`.
    - Content is split into chunks using `RecursiveCharacterTextSplitter`.
    - Chunks are converted into embeddings using HuggingFace's `all-MiniLM-L6-v2`.
    - Embeddings are stored in a local `ChromaDB` instance.

2. **Agent Phase (`agent.py`):**
    - The `uAgent` starts up and initializes a `RetrievalQA` chain.
    - When a `QuestionRequest` is received, the agent:
        - Searches ChromaDB for relevant document chunks.
        - Passes the chunks and the question to Gemini 2.0 Flash.
        - Sends the grounded answer back as an `AnswerResponse`.

## 11) Troubleshooting

- **ChromaDB Error:** If you get a "ChromaDB not found" warning, make sure you've run `python ingest.py` first.
- **Gemini Quota:** If you hit rate limits, the free tier of Gemini has specific RPS/RPM limits.
- **Missing Dependencies:** Ensure you've installed everything in `requirements.txt`.

## 12) License

This example is licensed under the Apache 2.0 License.
