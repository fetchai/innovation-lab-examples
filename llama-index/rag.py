import os
import re
import hashlib
import socket
import ipaddress
import tempfile
from urllib.parse import urlparse

import requests
from qdrant_client.http.exceptions import UnexpectedResponse

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.agent.workflow.workflow_events import ToolCallResult
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.vector_stores.qdrant import QdrantVectorStore

from config import (
    qclient,
    async_qclient,
    embed_model,
    llm,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    SIMILARITY_TOP_K,
    CHAT_MEMORY_TOKEN_LIMIT,
)

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

MAX_REDIRECTS = 5
MAX_FILENAME_LEN = 128

_user_sessions: dict[str, dict] = {}


def _collection_name(sender: str) -> str:
    return f"user_{hashlib.sha256(sender.encode()).hexdigest()[:32]}"


# ── SSRF protection ───────────────────────────────────────────────────


def _validate_url(url: str) -> str:
    """Validate URL scheme and resolve hostname to reject private/loopback IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Resolve hostname and check all resulting IPs
    try:
        addr_infos = socket.getaddrinfo(
            hostname, parsed.port or 443, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {e}") from e

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"URL resolves to non-public address: {ip}")

    return url


def _sanitize_filename(fname: str) -> str:
    """Strip directory components and unsafe characters from a filename."""
    fname = os.path.basename(fname)
    fname = re.sub(r"[^A-Za-z0-9._-]", "_", fname).strip("._")
    fname = fname[:MAX_FILENAME_LEN]
    return fname or "document"


# ── Document download ─────────────────────────────────────────────────


def download_document(url: str) -> str:
    """Download a document URL to a temp directory. Returns the local file path."""
    tmp_dir = tempfile.mkdtemp(prefix="rag_")

    # Validate initial URL
    _validate_url(url)

    # Manual redirect following with validation at each hop
    current_url = url
    resp = None
    for _ in range(MAX_REDIRECTS):
        resp = requests.get(current_url, timeout=120, allow_redirects=False)

        if resp.is_redirect or resp.is_permanent_redirect:
            redirect_url = resp.headers.get("Location")
            if not redirect_url:
                break
            _validate_url(redirect_url)
            current_url = redirect_url
            continue

        break

    if resp is None:
        raise RuntimeError("No response received")
    resp.raise_for_status()

    cd = resp.headers.get("Content-Disposition", "")
    if "filename=" in cd:
        fname = cd.split("filename=")[-1].strip('" ')
    else:
        fname = url.split("/")[-1].split("?")[0] or "document"

    fname = _sanitize_filename(fname)

    if "." not in fname:
        ct = resp.headers.get("Content-Type", "")
        if "pdf" in ct:
            fname += ".pdf"
        elif "html" in ct:
            fname += ".html"
        else:
            fname += ".txt"

    path = os.path.join(tmp_dir, fname)
    with open(path, "wb") as f:
        f.write(resp.content)

    print(f"[download] {len(resp.content)} bytes -> {path}")
    return path


# ── Ingestion ─────────────────────────────────────────────────────────


def _is_collection_not_found(exc: Exception) -> bool:
    """Check if an exception indicates a missing Qdrant collection."""
    if isinstance(exc, UnexpectedResponse) and exc.status_code == 404:
        return True
    if isinstance(exc, ValueError) and "not found" in str(exc).lower():
        return True
    return False


def clear_collection(collection_name: str):
    """Delete a Qdrant collection if it exists, so the next ingestion starts fresh."""
    try:
        qclient.delete_collection(collection_name)
        print(f"[qdrant] Deleted collection '{collection_name}'")
    except Exception as e:
        if _is_collection_not_found(e):
            return  # Collection didn't exist — that's fine
        raise


def ingest_document(
    file_path: str, collection_name: str, *, cleanup: bool = False
) -> int:
    """Ingest a local file into a Qdrant collection. Wipes old data first. Returns chunk count."""
    clear_collection(collection_name)

    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    print(f"[ingest] Loaded {len(documents)} page(s) from {file_path}")

    vector_store = QdrantVectorStore(client=qclient, collection_name=collection_name)

    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP),
            embed_model,
        ],
        vector_store=vector_store,
    )

    nodes = pipeline.run(documents=documents)
    print(f"[ingest] Stored {len(nodes)} chunks in '{collection_name}'")

    if cleanup:
        try:
            os.remove(file_path)
            os.rmdir(os.path.dirname(file_path))
        except OSError:
            pass

    return len(nodes)


# ── Agentic RAG (ReAct agent) ────────────────────────────────────────


def _build_agent_for_sender(sender: str) -> tuple[ReActAgent, ChatMemoryBuffer]:
    """Build a fresh ReAct agent backed by the user's Qdrant collection."""
    collection = _collection_name(sender)
    vector_store = QdrantVectorStore(
        client=qclient,
        aclient=async_qclient,
        collection_name=collection,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )

    query_engine = index.as_query_engine(similarity_top_k=SIMILARITY_TOP_K, llm=llm)

    doc_tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="document_search",
            description=(
                "Search the user's ingested documents. Use this tool "
                "to find specific metrics, dates, risk factors, revenue figures, "
                "or any content from the uploaded documents."
            ),
        ),
    )

    memory = ChatMemoryBuffer.from_defaults(token_limit=CHAT_MEMORY_TOKEN_LIMIT)

    react_agent = ReActAgent(
        tools=[doc_tool],
        llm=llm,
        verbose=True,
        system_prompt=(
            "You are a precise document analysis assistant. "
            "Answer questions using ONLY the content retrieved from the user's documents. "
            "Be direct and specific — no filler phrases like 'feel free to ask' or 'let me know if you need more'. "
            "When listing items, use clean formatting. "
            "If the documents don't contain the answer, say so plainly."
        ),
    )

    return react_agent, memory


def get_or_create_agent(sender: str) -> tuple[ReActAgent, ChatMemoryBuffer]:
    if sender in _user_sessions:
        return _user_sessions[sender]["agent"], _user_sessions[sender]["memory"]

    react_agent, memory = _build_agent_for_sender(sender)
    _user_sessions[sender] = {"agent": react_agent, "memory": memory}
    return react_agent, memory


async def query_agent(sender: str, query: str) -> tuple[str, list[dict]]:
    """Run a query through the user's ReAct agent. Returns (answer, citations)."""
    react_agent, memory = get_or_create_agent(sender)

    handler = react_agent.run(user_msg=query, memory=memory)

    # Collect tool call results as they stream for citation extraction
    tool_outputs = []
    async for event in handler.stream_events():
        if isinstance(event, ToolCallResult):
            tool_outputs.append(event.tool_output)

    result = await handler
    answer = (
        result.response.content
        if hasattr(result.response, "content")
        else str(result.response)
    )

    # Extract source nodes from query engine tool outputs
    citations = []
    for tool_output in tool_outputs:
        raw = tool_output.raw_output
        source_nodes = getattr(raw, "source_nodes", None) or []
        for node in source_nodes:
            citations.append(
                {
                    "page": node.node.metadata.get("page_label", "N/A"),
                    "file": node.node.metadata.get("file_name", "unknown"),
                    "score": node.score if node.score is not None else 0.0,
                    "excerpt": node.node.get_content().strip().replace("\n", " ")[:300],
                }
            )

    return answer, citations


MAX_DISPLAYED_SOURCES = 3


def _confidence_badge(score_pct: int) -> str:
    if score_pct >= 75:
        return f"High ({score_pct}%)"
    if score_pct >= 50:
        return f"Medium ({score_pct}%)"
    return f"Low ({score_pct}%)"


def _clean_excerpt(text: str, max_len: int = 250) -> str:
    """Trim excerpt to last full sentence within max_len."""
    excerpt = text[:max_len]
    for end in (".", "!", "?"):
        last = excerpt.rfind(end)
        if last > 60:
            return excerpt[: last + 1]
    return excerpt.rstrip() + "..."


def format_response_with_citations(answer: str, citations: list[dict]) -> str:
    if not citations:
        return answer

    # Deduplicate by page, keep highest score per page
    seen_pages: dict[str, dict] = {}
    for c in citations:
        page = c["page"]
        if page not in seen_pages or c["score"] > seen_pages[page]["score"]:
            seen_pages[page] = c
    unique = sorted(seen_pages.values(), key=lambda c: c["score"], reverse=True)

    shown = unique[:MAX_DISPLAYED_SOURCES]
    remaining = len(unique) - len(shown)

    parts = [
        answer,
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"**Retrieved from {len(unique)} source(s)**",
        "",
    ]

    for i, c in enumerate(shown, 1):
        score_pct = (
            int(c["score"] * 100) if isinstance(c["score"], float) else int(c["score"])
        )
        badge = _confidence_badge(score_pct)
        excerpt = _clean_excerpt(c["excerpt"])

        parts.append(f"**[{i}] Page {c['page']}** — {badge}")
        parts.append(f"> {excerpt}")
        parts.append("")

    if remaining > 0:
        parts.append(f"_+{remaining} more source(s) available_")

    return "\n".join(parts).rstrip()


def reset_user_session(sender: str):
    _user_sessions.pop(sender, None)


def collection_has_points(collection_name: str) -> bool:
    try:
        info = qclient.get_collection(collection_name)
        return info.points_count is not None and info.points_count > 0
    except Exception as e:
        if _is_collection_not_found(e):
            return False
        raise
