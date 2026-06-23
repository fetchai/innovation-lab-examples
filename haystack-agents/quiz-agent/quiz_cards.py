from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from uagents import Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    MetadataContent,
    TextContent,
)

CARD_PROTOCOL_VERSION = "1"
def _wrap(
    card_kind: str, payload: dict[str, Any], *, is_terminal: bool = False
) -> dict[str, str]:
    meta: dict[str, str] = {
        "card_protocol_version": CARD_PROTOCOL_VERSION,
        "requires_card_interaction": "true",
        "card_kind": card_kind,
        "card_payload": json.dumps(payload),
    }
    if is_terminal:
        meta["is_terminal"] = "true"
    return meta


class QuizCards:
    """Stateless factory of card metadata dicts."""
    def source_type_router_card(self) -> dict[str, str]:
        """``detail`` card: ask whether the user has a URL, a PDF, or both.

        Three plain CTAs — a single tap picks the path, no sub_options needed.
        """
        payload = {
            "title": "Choose Your Source Type",
            "summary_rows": [
                {"label": "URL", "value": "A website or Wikipedia article"},
                {"label": "PDF", "value": "A file you attach"},
                {"label": "Both", "value": "One or more of each"},
            ],
            "ctas": [
                {
                    "label": "URL",
                    "primary": True,
                    "selection": {"action": "choose_source_type", "source_type": "url"},
                },
                {
                    "label": "PDF",
                    "selection": {"action": "choose_source_type", "source_type": "pdf"},
                },
                {
                    "label": "Both",
                    "selection": {"action": "choose_source_type", "source_type": "both"},
                },
            ],
        }
        return _wrap("detail", payload)

    def source_intake_form(self, url_required: bool = True) -> dict[str, str]:
        """``form`` card collecting URLs, question count, difficulty, time limit.

        ``url_required=False`` is used whenever a PDF has already been
        captured — the user has a valid source even with no URL.
        """
        payload = {
            "title": "Set Up Your Quiz",
            "fields": [
                {
                    "name": "urls",
                    "kind": "text",
                    "label": (
                        "Source URLs (optional — you already added a PDF)"
                        if not url_required
                        else "Source URLs (comma-separated)"
                    ),
                    "required": url_required,
                    "placeholder": "https://example.com/a, https://example.com/b",
                },
                {
                    "name": "num_questions",
                    "kind": "select",
                    "label": "Number of questions",
                    "required": True,
                    "options": [
                        {"value": "5", "label": "5 questions"},
                        {"value": "10", "label": "10 questions"},
                        {"value": "15", "label": "15 questions"},
                        {"value": "20", "label": "20 questions"},
                    ],
                },
                {
                    "name": "difficulty",
                    "kind": "select",
                    "label": "Difficulty",
                    "required": True,
                    "options": [
                        {"value": "easy", "label": "Easy — recall & recognition"},
                        {"value": "medium", "label": "Medium — application & analysis"},
                        {"value": "hard", "label": "Hard — synthesis & evaluation"},
                    ],
                },
                {
                    "name": "time_limit",
                    "kind": "number",
                    "label": "Time limit in minutes (0 = no limit)",
                    "required": False,
                    "placeholder": "0",
                },
            ],
            "submit_cta": {
                "label": "Generate Quiz →",
                "selection": {"action": "generate_quiz"},
            },
        }
        return _wrap("form", payload)

    def question_card(
        self,
        q: dict[str, Any],
        q_num: int,
        total: int,
        time_remaining_secs: int | None = None,
    ) -> dict[str, str]:
        """``detail`` card: one question with A/B/C/D radio options.

        If ``time_remaining_secs`` is provided (and > 0), a "Time remaining"
        row is added so the user can track their personal countdown.
        """
        summary_rows: list[dict[str, str]] = [
            {"label": "Topic", "value": q.get("topic", "General")},
            {
                "label": "Difficulty",
                "value": str(q.get("difficulty", "medium")).capitalize(),
            },
        ]
        if time_remaining_secs is not None and time_remaining_secs > 0:
            mins, secs = divmod(int(time_remaining_secs), 60)
            summary_rows.append(
                {"label": "Time remaining", "value": f"{mins}m {secs:02d}s"}
            )
        payload = {
            "title": f"Question {q_num} of {total}",
            "summary_rows": summary_rows,
            "sub_options": {
                "name": "answer",
                "kind": "radio",
                "label": q["question"],
                "choices": [
                    {"value": "A", "label": f"A. {q['options']['A']}"},
                    {"value": "B", "label": f"B. {q['options']['B']}"},
                    {"value": "C", "label": f"C. {q['options']['C']}"},
                    {"value": "D", "label": f"D. {q['options']['D']}"},
                ],
            },
            "ctas": [
                {
                    "label": "Submit Answer →",
                    "primary": True,
                    "selection": {"action": "submit_answer", "q_id": q["q_id"]},
                }
            ],
        }
        return _wrap("detail", payload)

    def feedback_card(
        self, q: dict[str, Any], user_answer: str, is_correct: bool, *, is_last: bool = False
    ) -> dict[str, str]:
        """``detail`` card: grades the answer and cites the source passage.

        On the final question, ``is_last=True`` changes the CTA to "See Results →"
        so the user knows what comes next before tapping.
        """
        emoji = "✅" if is_correct else "❌"
        explanation = q.get("explanation", "")
        if len(explanation) > 350:
            explanation = explanation[:347] + "…"
        rows = [
            {
                "label": "Your answer:",
                "value": f"{user_answer}. {q['options'].get(user_answer, '?')}",
            },
        ]
        if not is_correct:
            rows.append(
                {
                    "label": "Correct answer:",
                    "value": f"{q['correct']}. {q['options'][q['correct']]}",
                }
            )
        rows.append({"label": "Why:", "value": explanation})
        rows.append(
            {"label": "Source:", "value": q.get("source_ref", "Source document")}
        )
        cta_label = "See Results →" if is_last else "Next Question →"
        payload = {
            "title": f"{emoji} {'Correct!' if is_correct else 'Incorrect'}",
            "summary_rows": rows,
            "ctas": [
                {
                    "label": cta_label,
                    "primary": True,
                    "selection": {"action": "next_question"},
                }
            ],
        }
        return _wrap("detail", payload)

    def results_card(
        self, state_data: dict[str, Any], weak_topics: list[str]
    ) -> dict[str, str]:
        """``detail`` card: score + grade + weak topics + four replay CTAs."""
        score = state_data["score"]
        total = len(state_data["questions"])
        pct = int((score / total) * 100) if total else 0
        grade = (
            "Excellent"
            if pct >= 90
            else "Good"
            if pct >= 70
            else "Needs Review"
        )
        payload = {
            "title": f"Quiz Complete — {score}/{total} ({pct}%)",
            "summary_rows": [
                {"label": "Grade", "value": grade},
                {"label": "Score", "value": f"{score} out of {total}"},
                {
                    "label": "Topics to review",
                    "value": ", ".join(weak_topics) if weak_topics else "None — Great job!",
                },
            ],
            "ctas": [
                {
                    "label": "Full Retake",
                    "primary": True,
                    "selection": {"action": "full_retake"},
                },
                {"label": "Weak Topics", "selection": {"action": "retry_weak"}},
                {"label": "Study Concept", "selection": {"action": "study_concept"}},
                {"label": "New Quiz", "selection": {"action": "new_quiz"}},
            ],
        }
        return _wrap("detail", payload)

    def study_card(self, topic: str, passage: dict[str, Any]) -> dict[str, str]:
        """detail card: a RAG-retrieved passage for the Study Concept feature."""
        text = (passage.get("text") or "").strip()
        # Keep only the first ~400 chars — enough to convey the key idea without
        # overwhelming the card. Strip any leading [source:...] tag inserted by
        # _join_docs so only clean content shows.
        if text.startswith("[source:"):
            text = text[text.find("]") + 1 :].lstrip()
        if len(text) > 600:
            text = text[:597] + "…"
        source = passage.get("source", "Your document")
        payload = {
            "title": f"📖 Study: {topic}",
            "summary_rows": [
                {"label": "Source:", "value": source},
                {
                    "label": "Key passage:",
                    "value": text or "No relevant passage found in your source material.",
                },
            ],
            "ctas": [
                {
                    "label": "← Back to Results",
                    "selection": {"action": "back_to_results"},
                },
            ],
        }
        return _wrap("detail", payload, is_terminal=False)


# Send helpers (shared by agent.py and payment_handler.py) 
async def send_card(
    ctx: Context, sender: str, text_narration: str, card: dict[str, str]
) -> None:
    """Send a ChatMessage carrying an optional text bubble + one card."""
    content: list[Any] = []
    if text_narration:
        content.append(TextContent(type="text", text=text_narration))
    content.append(MetadataContent(type="metadata", metadata=card))
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content
        ),
    )


async def send_text(ctx: Context, sender: str, text: str) -> None:
    """Send a plain-text ChatMessage (no card)."""
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )
