"""
RAG-powered Document Q&A Agent

A uAgent that ingests PDF or plain-text documents, embeds them with
HuggingFace sentence-transformers, stores vectors in ChromaDB, and
answers natural-language questions via the uAgents Chat Protocol
using Google Gemini 2.0 Flash as the LLM backbone.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from rag import get_answer, index_document, is_ready

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DOCUMENT_PATH = os.getenv("DOCUMENT_PATH", "")

SYSTEM_PROMPT = (
    "You are a document Q&A assistant. Answer questions strictly based on "
    "the retrieved document context. If the answer is not in the context, "
    "say you don't know. Do not hallucinate information. Cite relevant "
    "sections when possible."
)

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    user_text = "\n".join(
        item.text for item in msg.content if isinstance(item, TextContent) and item.text
    ).strip()

    if not user_text:
        welcome = (
            "Hi! I'm your Document Q&A Agent powered by RAG.\n\n"
            "Before asking questions, make sure a document has been ingested.\n"
            "You can ask me anything about the loaded document and I'll "
            "answer based on its content.\n\n"
            "Commands:\n"
            "  ingest <path>  — load a PDF or .txt file\n"
            "  status         — check if a document is loaded\n"
            "  <question>     — ask a question about the document\n"
        )
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=welcome)],
            ),
        )
        return

    if user_text.lower().startswith("ingest "):
        doc_path = user_text[7:].strip()
        if not doc_path:
            reply = "Please provide a file path after `ingest`."
        else:
            try:
                chunk_count = index_document(doc_path)
                reply = (
                    f"Document ingested successfully!\n"
                    f"Chunks stored: {chunk_count}\n"
                    f"You can now ask questions about the document."
                )
            except FileNotFoundError:
                reply = f"File not found: {doc_path}"
            except Exception as exc:
                reply = f"Error ingesting document: {exc}"
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=reply)],
            ),
        )
        return

    if user_text.lower().strip() == "status":
        if is_ready():
            reply = "A document is loaded and ready for questions."
        else:
            reply = (
                "No document is currently loaded. "
                "Use `ingest <path>` to load one, or set "
                "DOCUMENT_PATH in your .env file."
            )
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=reply)],
            ),
        )
        return

    if not is_ready():
        reply = (
            "No document is loaded yet. Please ingest a document first "
            "using `ingest <path>` or set DOCUMENT_PATH in your .env."
        )
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=reply)],
            ),
        )
        return

    try:
        answer = get_answer(user_text, system_prompt=SYSTEM_PROMPT)
    except Exception as exc:
        ctx.logger.exception("RAG query failed")
        answer = f"Sorry, I encountered an error: {exc}"

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=answer)],
        ),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}"
    )


agent = Agent()

agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(f"RAG Document Q&A Agent started at {agent.address}")
    ctx.logger.info(f"GEMINI_API_KEY configured: {bool(GEMINI_API_KEY)}")

    if DOCUMENT_PATH:
        try:
            chunk_count = index_document(DOCUMENT_PATH)
            ctx.logger.info(
                f"Auto-ingested document from DOCUMENT_PATH: "
                f"{DOCUMENT_PATH} ({chunk_count} chunks)"
            )
        except Exception as exc:
            ctx.logger.warning(f"Auto-ingest failed for {DOCUMENT_PATH}: {exc}")
    else:
        ctx.logger.info("No DOCUMENT_PATH set. Use `ingest <path>` to load a document.")


if __name__ == "__main__":
    agent.run()
