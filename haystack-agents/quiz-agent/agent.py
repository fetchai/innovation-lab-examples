from __future__ import annotations
import asyncio
import json
import os
import random
import re

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from payment_handler import (  # noqa: E402
    confirm_payment_via_text,
    payment_proto,
    request_payment,
)
from quiz_cards import QuizCards, send_card, send_text  # noqa: E402
from quiz_pipeline import QuizPipeline  # noqa: E402
from session_manager import (  # noqa: E402
    AWAITING_FILE_ATTACH,
    AWAITING_PAYMENT,
    AWAITING_SOURCES,
    CHOOSING_SOURCE_TYPE,
    COMPLETED,
    INDEXING,
    QUIZZING,
    UNINITIALIZED,
    SessionManager,
    compute_weak_topics,
)

agent = Agent(
    name=os.getenv("AGENT_NAME", "haystack-quiz-agent"),
    seed=os.environ.get("AGENT_SEED", "haystack-quiz-agent-dev-seed"),
    port=int(os.getenv("AGENT_PORT", "8080")),
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)
session = SessionManager()
pipeline = QuizPipeline()
cards = QuizCards()

_STRIPE_CONFIRM_RE = re.compile(r"^<stripe:payment_id:.+:CONFIRM>$")
_PAID_WORDS = {"paid", "done", "i've paid", "ive paid", "payment done", "continue"}


# Text / selection parsing helpers
def _extract_text(msg: ChatMessage) -> str:
    """Return the first TextContent block's text, stripped of @mention and file attachments.

    ASI:One appends file attachments as ``![filename.ext](url)`` markdown lines
    inside the same TextContent block. Strip them so downstream parsing only
    sees the human-typed text.
    """
    for block in msg.content:
        if isinstance(block, TextContent):
            text = re.sub(r"^@\S+\s+", "", (block.text or "")).strip()
            # Remove markdown image attachment lines (files attached via "Add files").
            text = re.sub(r"\n*!\[[^\]]*\]\(https?://[^)]+\)", "", text).strip()
            return text
    return ""


# ASI:One embeds file attachments as markdown image syntax inside TextContent:
#   ![panda.pdf](https://res.cloudinary.com/fetch-ai/raw/upload/...)
# There is no ResourceContent block — this is the actual wire format.
_PDF_MARKDOWN_RE = re.compile(
    r"!\[([^\]]*\.pdf[^\]]*)\]\((https?://[^)]+)\)", re.IGNORECASE
)


def _extract_pdf_uris(msg: ChatMessage, ctx: Context) -> list[str]:
    """Extract PDF Cloudinary URLs from ASI:One file attachments.

    ASI:One encodes attached files as markdown image syntax inside TextContent:
        ![panda.pdf](https://res.cloudinary.com/fetch-ai/raw/upload/...)
    We detect PDFs by matching ``![*.pdf](url)`` in the text of each block.
    """
    pdf_uris: list[str] = []
    for block in msg.content:
        if not isinstance(block, TextContent):
            continue
        for match in _PDF_MARKDOWN_RE.finditer(block.text or ""):
            filename = match.group(1)
            uri = match.group(2)
            ctx.logger.info(f"[agent] PDF attachment: {filename} → {uri[:80]}")
            pdf_uris.append(uri)
    return pdf_uris


# Trailing punctuation that text-embedded URLs should never end with.
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s,)>\"']+")


def _extract_plain_urls(text: str) -> list[str]:
    """Pull http(s) URLs out of free-form text (used in the file-attach step).

    Strips trailing punctuation (closing parens, brackets, quotes) that get
    attached when ASI:One embeds a file URL inside markdown-style text.
    Also excludes Cloudinary file-storage URLs — those are PDF attachments
    handled by _extract_pdf_uris, not browseable source content.
    """
    if not text:
        return []
    urls = []
    for u in _URL_IN_TEXT_RE.findall(text):
        u = u.rstrip(".,;:!?)>\"'")
        if "res.cloudinary.com" in u or "agentverse.ai/v1/storage" in u:
            continue
        urls.append(u)
    return urls


def _parse_answer(text: str) -> str | None:
    """Parse an A/B/C/D answer from selection JSON or free text."""
    try:
        parsed = json.loads(text)
        ans = str(parsed.get("answer", "")).upper()
        if ans in ("A", "B", "C", "D"):
            return ans
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\b([ABCD])\b", text.upper())
    return match.group(1) if match else None


def _parse_action(text: str) -> str:
    """Parse a card action from selection JSON or free text."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("action"):
            return parsed["action"]
    except (json.JSONDecodeError, TypeError):
        pass
    low = text.lower()
    if "retake" in low or "again" in low:
        return "full_retake"
    if "retry" in low or "weak" in low:
        return "retry_weak"
    if "study" in low:
        return "study_concept"
    if "new quiz" in low or "new" in low:
        return "new_quiz"
    return ""


def _parse_source_form(text: str) -> dict:
    """Parse the source intake form (selection JSON, or URLs from prose)."""
    result = {
        "urls": [],
        "pdf_b64": [],
        "num_questions": 10,
        "difficulty": "medium",
        "time_limit_mins": 0,
    }
    try:
        parsed = json.loads(text)
        urls_raw = parsed.get("urls", "") or ""
        result["urls"] = [
            u.strip() for u in urls_raw.split(",") if u.strip().startswith("http")
        ]
        result["num_questions"] = int(parsed.get("num_questions", 10) or 10)
        result["difficulty"] = parsed.get("difficulty", "medium") or "medium"
        result["time_limit_mins"] = int(parsed.get("time_limit", 0) or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        result["urls"] = re.findall(r"https?://[^\s,]+", text)
    return result


def _parse_topic_from_text(text: str, state_data: dict) -> str:
    """Pick a study topic: explicit JSON topic, else first weak topic."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("topic"):
            return parsed["topic"]
    except (json.JSONDecodeError, TypeError):
        pass
    weak = compute_weak_topics(state_data)
    return weak[0] if weak else "key concepts"


# Timer helper
def _time_remaining_secs(state_data: dict) -> int | None:
    """Return seconds left on the personal countdown, or None if no limit set."""
    import time as _t

    limit_mins = state_data.get("time_limit_mins", 0)
    start_ts = state_data.get("quiz_start_ts")
    if not limit_mins or not start_ts:
        return None
    remaining = (limit_mins * 60) - (_t.time() - start_ts)
    return max(0, int(remaining))


# Background tasks
async def _index_and_generate(ctx: Context, sender: str, parsed: dict) -> None:
    """Run Haystack indexing + generation, then start the quiz."""
    import time as _time

    state_data = session.get(ctx, sender)
    try:
        now = _time.time()
        doc_store_key = f"store:{sender}:{int(now)}"
        questions = await asyncio.to_thread(
            pipeline.index_and_generate,
            urls=parsed.get("urls", []),
            pdf_b64_list=parsed.get("pdf_b64", []),
            pdf_uris=parsed.get("pdf_uris", []),
            num_questions=parsed.get("num_questions", 10),
            difficulty=parsed.get("difficulty", "medium"),
            store_key=doc_store_key,
        )
        time_limit = int(parsed.get("time_limit_mins", 0) or 0)
        state_data.update(
            {
                "questions": questions,
                "original_questions": list(questions),
                "doc_store_key": doc_store_key,
                "current_q": 0,
                "answers": {},
                "score": 0,
                "state": QUIZZING,
                "time_limit_mins": time_limit,
                "quiz_start_ts": now if time_limit > 0 else None,
            }
        )
        session.save(ctx, sender, state_data)
        remaining = _time_remaining_secs(state_data)
        # If any source was skipped (e.g. PDF download failed), tell the user
        # once before the first question so they know what the quiz covers.
        failures = pipeline._last_failures
        if failures:
            skip_note = "; ".join(failures[:2])
            narration = f"Heads up — some sources couldn't be read ({skip_note}). Quiz is based on what was successfully indexed."
        else:
            narration = "Please answer the following questions."
        await send_card(
            ctx,
            sender,
            text_narration=narration,
            card=cards.question_card(questions[0], 1, len(questions), remaining),
        )
    except Exception as exc:  # noqa: BLE001 — surface any pipeline failure to user
        ctx.logger.error(f"[pipeline] index/generate failed: {exc}")
        state_data["state"] = AWAITING_SOURCES
        session.save(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            text_narration=(
                "Agent could not generate a quiz for this website or PDF. "
                "Please try a different source (e.g. a Wikipedia article or nationalzoo.si.edu)."
            ),
            card=cards.source_intake_form(),
        )


async def _regenerate_weak(ctx, sender, state_data, weak_topics):
    """Regenerate a focused mini-quiz from the user's weak topics."""
    difficulty = (
        state_data["questions"][0].get("difficulty", "medium")
        if state_data["questions"]
        else "medium"
    )
    try:
        questions = await asyncio.to_thread(
            pipeline.regenerate_for_topics,
            store_key=state_data.get("doc_store_key") or "",
            topics=weak_topics,
            num_questions=min(5, len(weak_topics) * 2 or 5),
            difficulty=difficulty,
        )
        # Preserve the original quiz questions so Full Retake can always restore them
        if not state_data.get("original_questions"):
            state_data["original_questions"] = list(state_data["questions"])
        state_data["questions"] = questions
        state_data["answers"] = {}
        state_data["score"] = 0
        state_data["current_q"] = 0
        state_data["state"] = QUIZZING
        # No timer on retries — the countdown only applies to the original quiz run.
        state_data["quiz_start_ts"] = None
        session.save(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            text_narration=f"Targeted re-quiz on {', '.join(weak_topics)} — {len(questions)} questions.",
            card=cards.question_card(questions[0], 1, len(questions)),
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"[pipeline] regenerate_weak failed: {exc}")
        await send_text(
            ctx,
            sender,
            "I couldn't regenerate a focused quiz (the source index may have expired after a "
            "restart). Use 'New Quiz' to rebuild from your sources.",
        )


# Chat handler (the state machine)
@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Drive the per-sender quiz state machine."""
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=msg.timestamp, acknowledged_msg_id=msg.msg_id),
    )

    text = _extract_text(msg)

    # Session-window tracking (hackflow pattern)
    current_window = str(ctx.session)
    stored_window = ctx.storage.get(f"quiz:window:{sender}")
    if stored_window and stored_window != current_window:
        ctx.logger.info(f"[agent] New chat window for {sender} — full session reset")
        session.save(ctx, sender, session.default_state())
    ctx.storage.set(f"quiz:window:{sender}", current_window)

    # Stripe confirm signal — check BEFORE all state logic
    if _STRIPE_CONFIRM_RE.match(text):
        ctx.logger.info(f"[agent] Stripe confirm from {sender}")
        if await confirm_payment_via_text(ctx, sender):
            return
        await send_text(
            ctx,
            sender,
            "Payment signal received but Stripe still shows unpaid. "
            "Wait a moment and send any message to retry.",
        )
        return

    state_data = session.get(ctx, sender)

    if not text and any(isinstance(c, StartSessionContent) for c in msg.content):
        await send_text(
            ctx,
            sender,
            "Hi! I build interactive quizzes from your sources. "
            "Send any message to start (a one-time $2.00 fee applies).",
        )
        return

    # UNINITIALIZED
    if state_data["state"] == UNINITIALIZED:
        pdf_uris = _extract_pdf_uris(msg, ctx)
        if pdf_uris:
            state_data["pending_pdf_uris"] = pdf_uris
            ctx.logger.info(f"[agent] Stored {len(pdf_uris)} PDF URI(s) pre-payment")
        # Any first message → RequestPayment only (no preceding text).
        # request_payment() saves state_data, so pending_pdf_uris persists.
        await request_payment(ctx, sender, state_data)
        return

    # AWAITING_PAYMENT
    if state_data["state"] == AWAITING_PAYMENT:
        # "paid" / "done" → verify the stored Stripe session.
        if text.lower() in _PAID_WORDS:
            if await confirm_payment_via_text(ctx, sender):
                return
            await send_text(
                ctx,
                sender,
                "Stripe shows the payment isn't completed yet. Finish the checkout "
                "form, then type 'paid' again.",
            )
            return
        # Any other message → re-issue a fresh RequestPayment
        # No text before it — same rule as the initial payment gate.
        await request_payment(ctx, sender, state_data)
        return

    # Hard gate: never proceed unpaid (shouldn't normally be hit).
    if not state_data.get("stripe_paid"):
        await request_payment(ctx, sender, state_data)
        return

    # CHOOSING_SOURCE_TYPE
    if state_data["state"] == CHOOSING_SOURCE_TYPE:
        source_type = None
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                source_type = payload.get("source_type")
        except (json.JSONDecodeError, TypeError):
            pass
        if not source_type:
            low = text.lower()
            if "pdf" in low and ("both" in low or "url" in low):
                source_type = "both"
            elif "pdf" in low:
                source_type = "pdf"
            elif "url" in low:
                source_type = "url"

        if source_type == "url":
            state_data["state"] = AWAITING_SOURCES
            session.save(ctx, sender, state_data)
            await send_card(
                ctx,
                sender,
                text_narration="Paste your source URL(s) below.",
                card=cards.source_intake_form(url_required=True),
            )
        elif source_type in ("pdf", "both"):
            state_data["state"] = AWAITING_FILE_ATTACH
            session.save(ctx, sender, state_data)
            narration = (
                "Attach your PDF(s) below and paste any URL(s) in the same "
                "message, then send."
                if source_type == "both"
                else "Attach your PDF(s) below and send any message (e.g. "
                "'ready') to continue."
            )
            await send_text(ctx, sender, narration)
        else:
            await send_card(
                ctx,
                sender,
                text_narration="Sorry, I didn't catch that — please pick one:",
                card=cards.source_type_router_card(),
            )
        return

    # AWAITING_FILE_ATTACH
    if state_data["state"] == AWAITING_FILE_ATTACH:
        new_pdf_uris = _extract_pdf_uris(msg, ctx)
        new_urls = _extract_plain_urls(text)

        if new_pdf_uris:
            state_data["pending_pdf_uris"] = (
                state_data.get("pending_pdf_uris", []) + new_pdf_uris
            )
        if new_urls:
            state_data["pending_urls"] = state_data.get("pending_urls", []) + new_urls

        have_pdf = bool(state_data.get("pending_pdf_uris"))
        have_url = bool(state_data.get("pending_urls"))

        if not have_pdf and not have_url:
            await send_text(
                ctx,
                sender,
                "I didn't find a PDF attachment or a URL in that message — "
                "please attach a PDF and/or paste a URL, then send again.",
            )
            return

        state_data["state"] = AWAITING_SOURCES
        session.save(ctx, sender, state_data)
        n_pdf = len(state_data.get("pending_pdf_uris", []))
        n_url = len(state_data.get("pending_urls", []))
        parts = []
        if n_pdf:
            parts.append(f"{n_pdf} PDF(s)")
        if n_url:
            parts.append(f"{n_url} URL(s)")
        await send_card(
            ctx,
            sender,
            text_narration=f"Received {' and '.join(parts)}, please finish setting up.",
            card=cards.source_intake_form(url_required=False),
        )
        return

    # AWAITING_SOURCES
    if state_data["state"] == AWAITING_SOURCES:
        parsed = _parse_source_form(text)
        parsed["pdf_uris"] = state_data.get("pending_pdf_uris", [])
        # Merge URLs from the form field + any captured in the file-attach step,
        # then deduplicate (preserving order) so the same URL isn't indexed twice.
        combined_urls = parsed.get("urls", []) + state_data.get("pending_urls", [])
        parsed["urls"] = list(dict.fromkeys(combined_urls))
        if (
            not parsed.get("urls")
            and not parsed.get("pdf_b64")
            and not parsed.get("pdf_uris")
        ):
            url_required = not bool(state_data.get("pending_pdf_uris"))
            await send_card(
                ctx,
                sender,
                text_narration="I need at least one source — paste a URL or attach a PDF.",
                card=cards.source_intake_form(url_required=url_required),
            )
            return
        state_data["sources"] = parsed
        state_data["time_limit_mins"] = parsed.get("time_limit_mins", 0)
        state_data["pending_pdf_uris"] = []
        state_data["pending_urls"] = []
        state_data["state"] = INDEXING
        session.save(ctx, sender, state_data)
        await send_text(
            ctx,
            sender,
            f"Quizzes Agent working on your request! Generating {parsed['num_questions']} {parsed['difficulty']} questions.",
        )
        asyncio.create_task(_index_and_generate(ctx, sender, parsed))
        return

    # INDEXING
    if state_data["state"] == INDEXING:
        await send_text(
            ctx, sender, "Still indexing and generating questions — hang tight! 🛠️"
        )
        return

    # QUIZZING
    if state_data["state"] == QUIZZING:
        await _handle_answer(ctx, sender, state_data, text)
        return

    # COMPLETED
    if state_data["state"] == COMPLETED:
        await _handle_completed(ctx, sender, state_data, text)
        return


async def _handle_answer(ctx, sender, state_data, text):
    """Grade an answer (or show results when user taps 'See Results →' / 'Next Question →')."""
    try:
        questions = state_data["questions"]
        current_q = state_data["current_q"]

        ctx.logger.info(
            f"[quiz] QUIZZING q={current_q + 1}/{len(questions)} "
            f"sender={sender[:16]}… text={text[:80]!r}"
        )
        action = _parse_action(text)
        if action == "next_question":
            # current_q may equal len(questions) here (after the last answer was saved),
            # which is exactly how "See Results →" reaches _finish_quiz safely.
            if current_q < len(questions):
                remaining = _time_remaining_secs(state_data)
                if remaining is not None and remaining <= 0:
                    await _finish_quiz(ctx, sender, state_data, timed_out=True)
                    return
                await send_card(
                    ctx,
                    sender,
                    text_narration=f"Question {current_q + 1} of {len(questions)}",
                    card=cards.question_card(
                        questions[current_q], current_q + 1, len(questions), remaining
                    ),
                )
            else:
                await _finish_quiz(ctx, sender, state_data)
            return

        # Only answer submissions reach here — safe to index.
        q = questions[current_q]
        answer = _parse_answer(text)
        if not answer:
            ctx.logger.warning(f"[quiz] Could not parse answer from: {text[:120]!r}")
            remaining = _time_remaining_secs(state_data)
            await send_card(
                ctx,
                sender,
                text_narration="Please select one of the options (A, B, C, or D).",
                card=cards.question_card(q, current_q + 1, len(questions), remaining),
            )
            return

        ctx.logger.info(f"[quiz] Answer={answer} correct={q['correct']}")
        state_data["answers"][q["q_id"]] = answer
        is_correct = answer == q["correct"]
        if is_correct:
            state_data["score"] += 1
        next_q = current_q + 1
        state_data["current_q"] = next_q
        session.save(ctx, sender, state_data)

        is_last = next_q >= len(questions)
        narration = (
            "Your Answer is Correct! Here is the explanation:"
            if is_correct
            else "Your Answer is Incorrect. Here is the explanation:"
        )
        await send_card(
            ctx,
            sender,
            text_narration=narration,
            card=cards.feedback_card(q, answer, is_correct, is_last=is_last),
        )
        # Results are sent when the user taps "See Results →" (action="next_question"
        # with current_q >= len(questions)), not here — giving them time to read feedback.

    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"[quiz] _handle_answer crashed: {exc}", exc_info=True)
        await send_text(
            ctx,
            sender,
            f"Something went wrong grading that answer ({exc}). "
            "Please try selecting your answer again.",
        )


async def _finish_quiz(ctx, sender, state_data, *, timed_out: bool = False):
    """Transition to COMPLETED and send the results card."""
    state_data["state"] = COMPLETED
    # Clear the timer — it only applies to the quiz session the user set up.
    # Retries, retakes, and studying after this point run without a countdown.
    state_data["quiz_start_ts"] = None
    session.save(ctx, sender, state_data)
    weak_topics = compute_weak_topics(state_data)
    narration = (
        "Your time is up! Here are your results."
        if timed_out
        else "The quiz is complete! Here are your results."
    )
    await send_card(
        ctx,
        sender,
        text_narration=narration,
        card=cards.results_card(state_data, weak_topics),
    )


async def _handle_completed(ctx, sender, state_data, text):
    """Handle the replay/study/new-quiz actions on the results card."""
    action = _parse_action(text)

    if action == "retry_weak":
        weak = compute_weak_topics(state_data)
        if not weak:
            await send_text(
                ctx, sender, "No weak topics — you aced it! Try 'New Quiz' instead."
            )
            return
        await send_text(
            ctx, sender, f"Generating a targeted quiz on: {', '.join(weak)}…"
        )
        asyncio.create_task(_regenerate_weak(ctx, sender, state_data, weak))

    elif action == "full_retake":
        # Always retake the original quiz, not a retry mini-quiz.
        original_qs = list(
            state_data.get("original_questions") or state_data["questions"]
        )
        random.shuffle(original_qs)
        state_data.update(
            {
                "answers": {},
                "score": 0,
                "current_q": 0,
                "state": QUIZZING,
                "questions": original_qs,
            }
        )
        session.save(ctx, sender, state_data)
        remaining = _time_remaining_secs(state_data)
        await send_card(
            ctx,
            sender,
            text_narration="Starting fresh — new question order!",
            card=cards.question_card(original_qs[0], 1, len(original_qs), remaining),
        )

    elif action == "study_concept":
        topic = _parse_topic_from_text(text, state_data)
        passage = await asyncio.to_thread(
            pipeline.retrieve_passage, topic, state_data.get("doc_store_key")
        )
        await send_card(
            ctx,
            sender,
            text_narration=f"Here's what your sources say about '{topic}':",
            card=cards.study_card(topic, passage),
        )

    elif action == "new_quiz":
        state_data.update(
            {
                "state": CHOOSING_SOURCE_TYPE,
                "questions": [],
                "answers": {},
                "score": 0,
                "current_q": 0,
                "sources": {},
                "time_limit_mins": 0,
                "quiz_start_ts": None,
                "pending_pdf_uris": [],
                "pending_urls": [],
            }
        )
        session.save(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            text_narration="Let's make a new quiz! How will you provide your source material?",
            card=cards.source_type_router_card(),
        )

    else:
        weak_topics = compute_weak_topics(state_data)
        await send_card(
            ctx,
            sender,
            text_narration="Here are your results:",
            card=cards.results_card(state_data, weak_topics),
        )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Log inbound acknowledgements."""
    ctx.logger.debug(f"ACK from {sender} for {msg.acknowledged_msg_id}")


@agent.on_event("startup")
async def startup(ctx: Context):
    """Log the address + Agentverse inspector link."""
    ctx.logger.info(f"[agent] {agent.name} | {agent.address}")
    port = os.getenv("AGENT_PORT", "8080")
    ctx.logger.info(
        f"[agent] Inspector: https://agentverse.ai/inspect/"
        f"?uri=http://127.0.0.1:{port}&address={agent.address}"
    )


agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
