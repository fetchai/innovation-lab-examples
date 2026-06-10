"""LangGraph-based answer composition loop for free-text job application questions.

Graph:  compose → critique ──(approved or max_iter)──► END
                      │
                 (not approved)
                      │
                    revise ──────────────────────────► critique

The loop runs at most MAX_REVISIONS times. At each critique step the LLM
evaluates the draft and either approves it or provides specific feedback.
If feedback is given the revise node incorporates it and the cycle repeats.
"""

from __future__ import annotations

import json
import re
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

MAX_REVISIONS = 2  # compose + up to 2 revise → critique cycles = max 5 LLM calls

UNKNOWN_MARKER = "<NEEDS_USER_INPUT>"

_COMPOSE_SYSTEM = (
    "You help a candidate answer a job application question. "
    "Write a concise, first-person answer (1–3 short paragraphs, max ~150 words). "
    "Ground every claim in the provided resume. "
    "Do NOT invent companies, dates, projects, or technologies not in the resume. "
    f"If the resume doesn't support a confident answer, reply exactly: {UNKNOWN_MARKER}"
)

_CRITIQUE_SYSTEM = (
    "You are a strict job application reviewer. "
    "Evaluate the draft answer against the question. "
    "Reply with valid JSON only: "
    '{"approved": true/false, "feedback": "specific improvement instructions or empty string if approved"}'
)

_REVISE_SYSTEM = (
    "You help a candidate improve a job application answer. "
    "Revise the draft based on the feedback provided. "
    "Keep it concise (1–3 paragraphs, max ~150 words) and grounded in the resume. "
    f"If the resume truly doesn't support a confident answer, reply exactly: {UNKNOWN_MARKER}"
)


class _State(TypedDict):
    question_label: str
    question_desc: str
    resume_text: str
    draft: str
    feedback: str
    approved: bool
    iterations: int
    asi_api_key: str
    asi_model: str


def _call(state: _State, system: str, user: str, max_tokens: int = 600) -> str:
    from openai import OpenAI
    client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=state["asi_api_key"])
    resp = client.chat.completions.create(
        model=state["asi_model"],
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def _compose(state: _State) -> _State:
    user = (
        f"Question: {state['question_label']}\n"
        f"Description: {state['question_desc'] or '(none)'}\n\n"
        f"Resume:\n{state['resume_text'][:4000]}\n\n"
        "Write the answer now."
    )
    draft = _call(state, _COMPOSE_SYSTEM, user, max_tokens=400)
    return {**state, "draft": draft, "feedback": "", "approved": False, "iterations": 0}


def _critique(state: _State) -> _State:
    user = (
        f"Question: {state['question_label']}\n"
        f"Description: {state['question_desc'] or '(none)'}\n\n"
        f"Draft answer:\n{state['draft']}\n\n"
        "Is this answer relevant, grounded in facts (not invented), and appropriately concise? "
        "Reply with JSON only."
    )
    raw = _call(state, _CRITIQUE_SYSTEM, user, max_tokens=200)
    try:
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        approved = bool(result.get("approved", False))
        feedback = str(result.get("feedback", ""))
    except Exception:  # noqa: BLE001 - malformed JSON → treat as approved to avoid loop
        approved = True
        feedback = ""
    return {**state, "approved": approved, "feedback": feedback}


def _revise(state: _State) -> _State:
    user = (
        f"Question: {state['question_label']}\n"
        f"Description: {state['question_desc'] or '(none)'}\n\n"
        f"Resume:\n{state['resume_text'][:4000]}\n\n"
        f"Current draft:\n{state['draft']}\n\n"
        f"Reviewer feedback:\n{state['feedback']}\n\n"
        "Write an improved answer now."
    )
    draft = _call(state, _REVISE_SYSTEM, user, max_tokens=400)
    return {**state, "draft": draft, "iterations": state["iterations"] + 1}


def _route(state: _State) -> str:
    if state["approved"] or state["iterations"] >= MAX_REVISIONS:
        return "end"
    return "revise"


def _build_graph():
    g = StateGraph(_State)
    g.add_node("compose", _compose)
    g.add_node("critique", _critique)
    g.add_node("revise", _revise)
    g.set_entry_point("compose")
    g.add_edge("compose", "critique")
    g.add_conditional_edges("critique", _route, {"end": END, "revise": "revise"})
    g.add_edge("revise", "critique")
    return g.compile()


_graph = None


def compose_answer(
    question_label: str,
    question_desc: Optional[str],
    resume_text: str,
    asi_api_key: str,
    asi_model: str = "asi1",
) -> Optional[str]:
    """Run the compose → critique → revise loop and return the best answer,
    or None if the resume doesn't support a confident answer."""
    global _graph
    if _graph is None:
        _graph = _build_graph()

    initial: _State = {
        "question_label": question_label,
        "question_desc": question_desc or "",
        "resume_text": resume_text,
        "draft": "",
        "feedback": "",
        "approved": False,
        "iterations": 0,
        "asi_api_key": asi_api_key,
        "asi_model": asi_model,
    }

    try:
        final = _graph.invoke(initial)
    except Exception:  # noqa: BLE001 - best-effort; fall back to None
        return None

    draft = (final.get("draft") or "").strip()
    if not draft or UNKNOWN_MARKER in draft:
        return None
    return draft
