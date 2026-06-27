"""
RAG pipeline: document loading, chunking, embedding, vector storage,
and retrieval-augmented question answering using LangChain + Gemini.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

PERSIST_DIR = "chroma_db"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "gemini-2.0-flash"

_vectorstore: Chroma | None = None
_retriever: Any = None
_chat_history: list = []


def _load_pdf(path: str) -> str:
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _load_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _load_pdf(path)
    if ext in (".txt", ".md", ".csv"):
        return _load_text(path)
    raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .txt, .md, or .csv")


def index_document(path: str) -> int:
    global _vectorstore, _retriever, _chat_history

    text = load_document(path)
    if not text.strip():
        raise ValueError("Document is empty or could not be read.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = splitter.create_documents([text])

    if not chunks:
        raise ValueError("No chunks produced from document.")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )
    _retriever = _vectorstore.as_retriever(search_kwargs={"k": 4})
    _chat_history = []

    return len(chunks)


def is_ready() -> bool:
    global _vectorstore, _retriever
    if _vectorstore is not None and _retriever is not None:
        return True
    if os.path.isdir(PERSIST_DIR):
        try:
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            _vectorstore = Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=embeddings,
            )
            _retriever = _vectorstore.as_retriever(search_kwargs={"k": 4})
            return True
        except Exception:
            return False
    return False


def get_answer(question: str, system_prompt: str | None = None) -> str:
    global _chat_history

    if not is_ready():
        return "No document is loaded. Please ingest a document first."

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    default_system = (
        "You are a document Q&A assistant. Answer questions based strictly "
        "on the provided context. If the answer is not in the context, "
        "say 'I don't have enough information in the document to answer "
        "that question.' Do not make up information."
    )
    system_text = system_prompt or default_system

    docs = _retriever.invoke(question)
    context_text = "\n\n---\n\n".join(doc.page_content for doc in docs)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("system", "Document context:\n\n{context}"),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )

    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=gemini_api_key,
        temperature=0.2,
    )

    chain = prompt | llm | StrOutputParser()

    _chat_history.append(("human", question))

    result = chain.invoke(
        {
            "context": context_text,
            "question": question,
            "chat_history": _chat_history[-6:],
        }
    )

    _chat_history.append(("ai", result))

    return result
