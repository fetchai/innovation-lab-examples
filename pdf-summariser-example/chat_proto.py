import base64
import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    ResourceContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.storage import ExternalStorage

from utils import get_pdf_text, summarize_text

STORAGE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"
DOWNLOADS_DIR = "downloads"

chat_proto = Protocol(spec=chat_protocol_spec)


def create_text_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def create_metadata(metadata: dict[str, str]) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[MetadataContent(type="metadata", metadata=metadata)],
    )


def download_resource(ctx: Context, item: ResourceContent) -> dict | None:
    """Download PDF bytes from Agentverse storage, with fallback to URI if available."""
    # Try storage first
    try:
        ctx.logger.info(f"Downloading resource via storage: {item.resource_id}")
        storage = ExternalStorage(
            identity=ctx.agent.identity,
            storage_url=STORAGE_URL,
        )
        stored = storage.download(str(item.resource_id))
        mime_type = stored.get("mime_type", "application/pdf")
        content_bytes = base64.b64decode(stored.get("contents", ""))
    except Exception as exc:
        # Fallback: try downloading from URI if available
        ctx.logger.info(f"Storage download failed: {exc}, trying URI fallback...")
        if hasattr(item, "resource") and item.resource:
            uri = getattr(item.resource[0], "uri", None)
            if uri:
                try:
                    ctx.logger.info(f"Downloading resource via URI: {uri}")
                    response = httpx.get(uri, timeout=120)
                    response.raise_for_status()
                    content_bytes = response.content
                    mime_type = response.headers.get("content-type", "application/pdf")
                except Exception as uri_exc:
                    ctx.logger.error(f"URI download also failed: {uri_exc}")
                    return None
            else:
                return None
        else:
            return None

    if not mime_type.startswith("application/pdf"):
        ctx.logger.info(
            f"Overriding mime_type {mime_type} -> application/pdf for processing"
        )
        mime_type = "application/pdf"

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    filename = (
        f"{DOWNLOADS_DIR}/pdf_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    with open(filename, "wb") as pdf_file:
        pdf_file.write(content_bytes)
    ctx.logger.info(f"Saved resource locally to {filename}")

    return {
        "type": "resource",
        "mime_type": mime_type,
        "contents": base64.b64encode(content_bytes).decode("utf-8"),
    }


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Got a message from {sender}")

    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id, timestamp=datetime.now(timezone.utc)
        ),
    )

    prompt_content: list[dict] = []

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info("Session started, advertising attachment support")
            await ctx.send(sender, create_metadata({"attachments": "true"}))

        elif isinstance(item, TextContent):
            ctx.logger.info("Received text content")
            prompt_content.append({"type": "text", "text": item.text})

        elif isinstance(item, ResourceContent):
            ctx.logger.info(f"Received resource: {item.resource_id}")
            data = download_resource(ctx, item)
            if not data:
                await ctx.send(sender, create_text_chat("Failed to download PDF."))
                return
            prompt_content.append(data)

        elif isinstance(item, MetadataContent):
            ctx.logger.info(f"Received metadata: {item.metadata}")

        else:
            ctx.logger.warning(f"Unhandled content type: {type(item).__name__}")

    has_pdf = any(entry.get("type") == "resource" for entry in prompt_content)
    if not has_pdf:
        await ctx.send(
            sender,
            create_text_chat(
                "I didn't receive any PDFs in your message. Please attach a PDF."
            ),
        )
        return

    try:
        ctx.logger.info("Extracting text from PDF(s)...")
        extracted_text = get_pdf_text(prompt_content, logger=ctx.logger)
        
        if not extracted_text or extracted_text == "No PDF content found to extract.":
            await ctx.send(sender, create_text_chat("No text found in PDF."))
            return
        
        ctx.logger.info("Summarizing extracted text...")
        summary = summarize_text(extracted_text, logger=ctx.logger)
        
        if summary:
            await ctx.send(sender, create_text_chat(summary))
        else:
            # Fallback: send extracted text if summarization fails
            ctx.logger.warning("Summarization failed, sending extracted text instead")
            await ctx.send(sender, create_text_chat(extracted_text))
            
    except Exception as err:
        ctx.logger.error(f"PDF extraction failed: {err}")
        await ctx.send(
            sender,
            create_text_chat(
                "Sorry, I couldn't read that PDF. Please try again with a different file."
            ),
        )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )

