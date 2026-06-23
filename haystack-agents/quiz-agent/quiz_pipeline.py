from __future__ import annotations
import base64
import json
import os
import tempfile
from typing import Any

from haystack import Document, Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.converters import HTMLToDocument, PyPDFToDocument
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.components.writers import DocumentWriter
from haystack.dataclasses import ChatMessage
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.utils import Secret

ASI1_BASE_URL = "https://api.asi1.ai/v1"
_MAX_CONTEXT_CHARS = 14_000

_QUESTION_SYSTEM_PROMPT = """\
You are an expert quiz generator. Using ONLY the document excerpts provided, \
generate exactly {{ num_questions }} multiple-choice questions at {{ difficulty }} difficulty.

Rules:
- Each question must be answerable solely from the provided text. No outside knowledge.
- Each question has exactly four options keyed "A", "B", "C", "D"; exactly one is correct.
- "explanation" must be 1-2 concise sentences (under 250 characters) teaching WHY the correct answer is right and, if relevant, why the most tempting wrong option is wrong. State the key fact in plain language — do NOT paste a long raw quote from the source. The source URL is shown separately, so do not repeat it in the explanation.
- "source_ref" MUST be the source URL or filename the question came from.
- "topic" is a short (1-4 word) label for the concept tested.

Return ONLY valid JSON, no markdown fences, no preamble, in exactly this shape:
{
  "questions": [
    {
      "q_id": "q1",
      "question": "...",
      "topic": "...",
      "difficulty": "{{ difficulty }}",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "A",
      "explanation": "The correct answer is right because... (the wrong options are wrong because...)",
      "source_ref": "https://... or filename.pdf"
    }
  ]
}
"""

_QUESTION_USER_PROMPT = """\
Document excerpts:
---
{{ context }}
---
{% if topics %}
STRICT REQUIREMENT: Generate questions ONLY about these exact topics: {{ topics }}.
- Every question's "topic" field MUST be one of: {{ topics }}.
- Do NOT generate questions about any other subject, even if the text covers other areas.
{% endif %}
Generate the questions now."""


class QuizPipeline:
    """Owns the Haystack indexing, generation, and retrieval pipelines."""

    # Ligatures that pypdf/HTML extraction sometimes produce as single Unicode
    # characters. Normalizing them prevents an LLM from quoting an odd-looking
    # glyph verbatim in a question's explanation.
    _LIGATURE_MAP = {
        "ﬀ": "ff",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "st",
        "ﬆ": "st",
    }

    def __init__(self) -> None:
        self._stores: dict[str, InMemoryDocumentStore] = {}
        self._asi1_model = os.getenv("ASI1_MODEL", "asi1")
        # Reset at the start of every _index() call; read afterward by
        # index_and_generate() to build a specific error message.
        self._last_failures: list[str] = []

    @classmethod
    def _sanitize_text(cls, text: str) -> str:
        """Normalize ligatures and strip non-printable control characters.

        Applied to every extracted document regardless of source type.
        """
        if not text:
            return text
        for lig, replacement in cls._LIGATURE_MAP.items():
            text = text.replace(lig, replacement)
        return "".join(ch for ch in text if ch in "\n\t\r" or ch.isprintable())

    def index_and_generate(
        self,
        *,
        urls: list[str],
        pdf_b64_list: list[str],
        pdf_uris: list[str] | None = None,
        num_questions: int,
        difficulty: str,
        store_key: str,
    ) -> list[dict[str, Any]]:
        """Index sources then generate ``num_questions`` grounded questions."""
        self._last_failures = []
        store = self._index(
            urls=urls,
            pdf_b64_list=pdf_b64_list,
            pdf_uris=pdf_uris or [],
            store_key=store_key,
        )
        context = self._context_from_store(store)
        if not context.strip():
            detail = (
                " Details: " + "; ".join(self._last_failures)
                if self._last_failures
                else ""
            )
            raise RuntimeError(
                "No readable content was extracted from the provided sources." + detail
            )
        return self._generate_questions(
            context=context, num_questions=num_questions, difficulty=difficulty
        )

    # Common stopwords that are too generic to be useful for topic matching.
    _STOPWORDS = frozenset(
        {
            "the",
            "a",
            "an",
            "of",
            "in",
            "for",
            "on",
            "with",
            "to",
            "and",
            "is",
            "are",
            "was",
        }
    )

    def regenerate_for_topics(
        self, *, store_key: str, topics: list[str], num_questions: int, difficulty: str
    ) -> list[dict[str, Any]]:
        store = self._stores.get(store_key)
        if store is None:
            raise RuntimeError("Source index is no longer available. Start a new quiz.")
        context = self._context_for_topics(store, topics)
        # Generate 3× the target — gives a big enough pool even if the LLM
        # produces some malformed questions or the filter trims a few.
        raw = self._generate_questions(
            context=context,
            num_questions=max(num_questions * 3, num_questions + 5),
            difficulty=difficulty,
            topics=topics,
        )
        # Word-level filter: split each topic into individual keywords and check
        # whether any keyword appears in the question's topic field or text.
        # This is more forgiving than full-phrase matching (e.g. "panda adaptations"
        # → words ["panda", "adaptations"] each checked independently).
        topic_words = {
            w for t in topics for w in t.lower().split() if w not in self._STOPWORDS
        }
        filtered = (
            [
                q
                for q in raw
                if any(
                    word in q.get("topic", "").lower()
                    or word in q.get("question", "").lower()
                    for word in topic_words
                )
            ]
            if topic_words
            else raw
        )
        # Deduplicate by first 80 chars of question text.
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for q in filtered or raw:
            key = q["question"].lower()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(q)
        return unique[:num_questions]

    def retrieve_passage(self, topic: str, store_key: str | None) -> dict[str, Any]:
        """BM25-retrieve the most relevant passage for topic.

        Joins the top-3 matching chunks to give a broader, more informative
        passage than a single 5-sentence split would provide.
        """
        store = self._stores.get(store_key or "")
        if store is None:
            return {"text": "", "source": "—"}

        retriever = InMemoryBM25Retriever(document_store=store, top_k=3)
        docs = retriever.run(query=topic)["documents"]

        if not docs:
            all_docs = store.filter_documents()
            if not all_docs:
                return {"text": "", "source": "—"}
            docs = all_docs[:3]

        # Join the top chunks into one passage for richer context.
        combined = " ".join(d.content or "" for d in docs if d.content).strip()
        source = (
            docs[0].meta.get("source_ref") or docs[0].meta.get("url") or "Your document"
        )
        return {"text": combined, "source": source}

    def _index(
        self,
        *,
        urls: list[str],
        pdf_b64_list: list[str],
        pdf_uris: list[str] | None = None,
        store_key: str,
    ) -> InMemoryDocumentStore:
        """Fetch + convert sources into a BM25-ready document store."""
        store = InMemoryDocumentStore()
        self._stores[store_key] = store

        raw_docs: list[Document] = []
        raw_docs.extend(self._docs_from_urls(urls))
        raw_docs.extend(self._docs_from_pdfs(pdf_b64_list))
        raw_docs.extend(self._docs_from_pdf_uris(pdf_uris or []))

        for doc in raw_docs:
            if doc.content:
                doc.content = self._sanitize_text(doc.content)

        raw_docs = [d for d in raw_docs if d.content and d.content.strip()]
        if not raw_docs:
            return store

        indexing = Pipeline()
        indexing.add_component(
            "cleaner",
            DocumentCleaner(remove_empty_lines=True, remove_extra_whitespaces=True),
        )
        indexing.add_component(
            "splitter",
            DocumentSplitter(split_by="sentence", split_length=5, split_overlap=2),
        )
        indexing.add_component("writer", DocumentWriter(document_store=store))
        indexing.connect("cleaner", "splitter")
        indexing.connect("splitter", "writer")
        indexing.run({"cleaner": {"documents": raw_docs}})
        return store

    # Browser-like user-agents rotated across retries.
    _USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    ]
    # Full browser header set that passes Wikipedia's and most CDN bot checks.
    # httpx alone sends ~3 headers; real Chrome sends 15+. The Sec-Fetch-* family
    # is checked by many anti-bot systems and missing it is a strong bot signal.
    _REQUEST_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    def _docs_from_urls(self, urls: list[str]) -> list[Document]:
        """Fetch each URL and convert to Document(s).

        Wikipedia article URLs are routed through the MediaWiki API (which always
        returns clean plain text). All other URLs use LinkContentFetcher + HTMLToDocument.
        """
        clean_urls = [u for u in urls if u.strip().startswith("http")]
        if not clean_urls:
            return []

        wiki_urls = [u for u in clean_urls if "wikipedia.org/wiki/" in u]
        other_urls = [u for u in clean_urls if "wikipedia.org/wiki/" not in u]

        docs: list[Document] = []
        docs.extend(self._docs_from_wikipedia(wiki_urls))

        if other_urls:
            streams = LinkContentFetcher(
                raise_on_failure=False,
                user_agents=self._USER_AGENTS,
                request_headers=self._REQUEST_HEADERS,
            ).run(urls=other_urls)["streams"]
            if len(streams) < len(other_urls):
                missed = len(other_urls) - len(streams)
                self._last_failures.append(
                    f"{missed} URL(s) could not be fetched (site may block bots "
                    "or be unreachable)"
                )
            if streams:
                html_docs = HTMLToDocument().run(sources=streams)["documents"]
                for doc in html_docs:
                    doc.meta.setdefault("source_ref", doc.meta.get("url", "web source"))
                docs.extend(html_docs)

        return docs

    def _docs_from_wikipedia(self, urls: list[str]) -> list[Document]:
        """Fetch Wikipedia articles via the MediaWiki API (plain text, no bot blocks)."""
        if not urls:
            return []
        import httpx

        wiki_ua = (
            "HaystackQuizAgent/1.0 (https://github.com/fetchai/innovation-lab-examples)"
        )
        docs: list[Document] = []
        for url in urls:
            try:
                # Extract the article title from the URL path.
                title = url.split("/wiki/", 1)[1].split("#")[0]
                r = httpx.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": title,
                        "prop": "extracts",
                        "explaintext": "1",
                        "exsectionformat": "plain",
                        "format": "json",
                    },
                    headers={"User-Agent": wiki_ua},
                    timeout=15,
                    follow_redirects=True,
                )
                r.raise_for_status()
                pages = r.json().get("query", {}).get("pages", {})
                page = next(iter(pages.values()))
                text = (page.get("extract") or "").strip()
                if text:
                    docs.append(
                        Document(content=text, meta={"source_ref": url, "url": url})
                    )
                else:
                    self._last_failures.append(
                        f"Wikipedia article not found or empty: {url}"
                    )
            except Exception as exc:  # noqa: BLE001
                self._last_failures.append(
                    f"Could not fetch Wikipedia article {url}: {exc}"
                )
        return docs

    def _docs_from_pdfs(self, pdf_b64_list: list[str]) -> list[Document]:
        """Decode base64 PDFs to temp files and convert to Document(s)."""
        if not pdf_b64_list:
            return []
        paths: list[str] = []
        for i, b64 in enumerate(pdf_b64_list):
            try:
                data = base64.b64decode(b64)
            except (ValueError, TypeError):
                self._last_failures.append(f"PDF #{i + 1} was not valid base64 data")
                continue
            tmp = tempfile.NamedTemporaryFile(suffix=f"_{i}.pdf", delete=False)
            tmp.write(data)
            tmp.close()
            paths.append(tmp.name)
        if not paths:
            return []
        docs = PyPDFToDocument().run(sources=paths)["documents"]
        for doc, path in zip(docs, paths):
            doc.meta.setdefault("source_ref", os.path.basename(path))
        return docs

    def _docs_from_pdf_uris(self, pdf_uris: list[str]) -> list[Document]:
        """Download PDFs from Agentverse External Storage and convert them.

        ASI:One uploads attached files to Agentverse External Storage and
        sends a URI reference, not inline bytes. URI format:
        ``agent-storage://agentverse.ai/v1/storage/{asset_id}`` — converted
        to HTTPS for the actual download, authenticated with AGENTVERSE_API_KEY.
        """
        if not pdf_uris:
            return []
        import requests  # noqa: PLC0415

        api_token = (os.getenv("AGENTVERSE_API_KEY") or "").strip()
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        docs: list[Document] = []

        for uri in pdf_uris:
            # Strip any trailing punctuation that text-extraction may have appended.
            uri = uri.rstrip(".,;:!?)>\"'")

            if uri.startswith("agent-storage://"):
                https_url = "https://" + uri[len("agent-storage://") :]
            elif uri.startswith("http"):
                https_url = uri
            else:
                self._last_failures.append(
                    f"Skipped unrecognized PDF reference: {uri[:60]}"
                )
                continue

            # Cloudinary and other public CDNs do not need auth; only send the
            # Bearer token for known Agentverse storage endpoints.
            req_headers = headers if "agentverse.ai" in https_url else {}

            tmp_path = None
            try:
                resp = requests.get(https_url, headers=req_headers, timeout=30)
                resp.raise_for_status()
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.write(resp.content)
                tmp.close()
                tmp_path = tmp.name

                pdf_docs = PyPDFToDocument().run(sources=[tmp_path])["documents"]
                usable = [d for d in pdf_docs if d.content and d.content.strip()]
                if not usable:
                    self._last_failures.append(
                        f"PDF at ...{uri[-40:]} produced no extractable text "
                        "(it may be a scanned image with no text layer)"
                    )
                for doc in pdf_docs:
                    doc.meta.setdefault("source_ref", uri)
                docs.extend(pdf_docs)
            except Exception as exc:  # noqa: BLE001
                self._last_failures.append(
                    f"Could not download/read PDF from storage: {exc}"
                )
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        return docs

    def _context_from_store(self, store: InMemoryDocumentStore) -> str:
        """Build context by round-robining chunks across all sources.

        Naive insertion-order concatenation lets a single large source (e.g. a
        long Wikipedia article) fill the entire context window before any PDF
        chunks are included. Interleaving ensures every source contributes
        proportionally to the 14 k-char cap regardless of relative size.
        """
        from itertools import zip_longest  # noqa: PLC0415

        all_docs = store.filter_documents()
        groups: dict[str, list[Document]] = {}
        for doc in all_docs:
            src = doc.meta.get("source_ref", "unknown")
            groups.setdefault(src, []).append(doc)

        # One chunk per source per round until all lists are exhausted.
        interleaved: list[Document] = []
        for row in zip_longest(*groups.values()):
            interleaved.extend(d for d in row if d is not None)

        return self._join_docs(interleaved)

    def _context_for_topics(
        self, store: InMemoryDocumentStore, topics: list[str]
    ) -> str:
        """BM25-retrieve chunks relevant to each weak topic, deduplicated."""
        seen_ids: set[str] = set()
        matched: list[Document] = []
        for topic in topics:
            try:
                retriever = InMemoryBM25Retriever(document_store=store, top_k=5)
                docs = retriever.run(query=topic)["documents"]
                for doc in docs:
                    if doc.id not in seen_ids:
                        seen_ids.add(doc.id)
                        matched.append(doc)
            except Exception:  # noqa: BLE001
                pass
        return self._join_docs(matched or store.filter_documents())

    @staticmethod
    def _join_docs(docs: list[Document]) -> str:
        """Join documents into a single capped, source-tagged context string."""
        parts: list[str] = []
        used = 0
        for doc in docs:
            src = doc.meta.get("source_ref", "source")
            chunk = f"[source: {src}]\n{doc.content or ''}\n"
            if used + len(chunk) > _MAX_CONTEXT_CHARS:
                break
            parts.append(chunk)
            used += len(chunk)
        return "\n".join(parts)

    def _generate_questions(
        self,
        *,
        context: str,
        num_questions: int,
        difficulty: str,
        topics: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run the generation pipeline, retrying until valid JSON parses."""
        pipe = Pipeline()
        pipe.add_component(
            "prompt",
            ChatPromptBuilder(
                template=[
                    ChatMessage.from_system(_QUESTION_SYSTEM_PROMPT),
                    ChatMessage.from_user(_QUESTION_USER_PROMPT),
                ],
                required_variables="*",
            ),
        )
        pipe.add_component(
            "llm",
            OpenAIChatGenerator(
                api_key=Secret.from_env_var("ASI1_API_KEY"),
                api_base_url=ASI1_BASE_URL,
                model=self._asi1_model,
                generation_kwargs={"max_tokens": 4096},
            ),
        )
        pipe.connect("prompt", "llm")

        variables = {
            "num_questions": num_questions,
            "difficulty": difficulty,
            "context": context,
            "topics": ", ".join(topics) if topics else "",
        }

        last_error = ""
        for _ in range(3):
            result = pipe.run({"prompt": variables})
            reply = result["llm"]["replies"][0].text or ""
            questions = self._parse_questions(reply)
            if questions:
                return questions[:num_questions]
            last_error = reply[:200]
        raise RuntimeError(
            f"Question generation returned invalid JSON. Last reply: {last_error}"
        )

    @staticmethod
    def _parse_questions(reply: str) -> list[dict[str, Any]]:
        """Extract and validate the questions array from an LLM reply."""
        text = reply.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
        questions = data.get("questions", [])
        valid: list[dict[str, Any]] = []
        for i, q in enumerate(questions):
            opts = q.get("options", {})
            if not all(k in opts for k in ("A", "B", "C", "D")):
                continue
            if q.get("correct") not in ("A", "B", "C", "D"):
                continue
            q["q_id"] = q.get("q_id") or f"q{i + 1}"
            q.setdefault("topic", "General")
            q.setdefault("difficulty", "medium")
            q.setdefault("explanation", "")
            q.setdefault("source_ref", "Source document")
            valid.append(q)
        return valid
