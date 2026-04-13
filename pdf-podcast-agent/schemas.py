"""
Shared Pydantic data models for the PDF-to-Podcast agent pipeline.
All four agents exchange these schemas so the LLM can never hallucinate formats.
"""

from uagents import Model
from typing import List


# ── 1. Orchestrator → Extractor ──────────────────────────────────────────────


class ExtractRequest(Model):
    """Raw document text sent by the Orchestrator to the RAG Extractor."""

    document_text: str
    session_id: str


# ── 2. Extractor → Scriptwriter ──────────────────────────────────────────────


class ResearchInsights(Model):
    """Distilled key facts returned by the RAG Extractor."""

    core_thesis: str
    key_metrics: List[str]
    controversial_point: str
    session_id: str


# ── 3. Scriptwriter → Voice Studio ───────────────────────────────────────────


class DialogueLine(Model):
    """A single line of spoken dialogue (speaker + text)."""

    speaker: str  # "HostA" (skeptic) or "HostB" (expert)
    text: str


class PodcastScript(Model):
    """Full back-and-forth dialogue script returned by the Scriptwriter."""

    lines: List[DialogueLine]
    topic_title: str
    session_id: str


# ── 4. Voice Studio → Orchestrator ───────────────────────────────────────────


class AudioResponse(Model):
    """Stitched MP3 returned by the Voice Studio."""

    audio_base64: str  # base64-encoded final MP3 bytes
    audio_path: str  # local path where the MP3 was saved
    session_id: str
    line_count: int


# ── 5. Debate chain (Orchestrator ↔ Host Agents) ─────────────────────────────


class DebateTurn(Model):
    """Orchestrator → Host: request one debate turn."""

    session_id: str
    topic_title: str
    core_thesis: str
    key_metrics: List[str]
    controversial_point: str
    document_snippet: str
    user_address: str  # ASI:One user to stream the debate to
    turn: int  # 0-indexed
    max_turns: int
    previous_statement: str  # opponent's last line (empty on turn 0)
    speaker_personality: str = ""  # system-prompt personality hint for this host
    debate_history: str = ""  # full conversation so far (all prior turns)


class DebateResponse(Model):
    """Host → Orchestrator: the generated debate line for this turn."""

    session_id: str
    speaker: str  # "skeptic" | "expert"
    reply_text: str
    turn: int
    max_turns: int
    user_address: str
    topic_title: str
    core_thesis: str
    key_metrics: List[str]
    controversial_point: str
    document_snippet: str


# ── 6. Orchestrator → Host Agents (context injection) ────────────────────────


class ContextInjection(Model):
    """Sent by the Orchestrator to @HostA and @HostB after the pipeline runs.

    The two host agents persist this in ctx.storage so they can answer
    follow-up questions from users in ASI:One's chat interface.
    """

    session_id: str  # UUID; agents store context keyed by this
    topic_title: str
    core_thesis: str
    key_metrics: List[str]
    controversial_point: str
    document_snippet: str  # first 4 000 chars of the source doc for Q&A depth
    host_a_personality: str = ""  # system-prompt personality hint for Host A
    host_b_personality: str = ""  # system-prompt personality hint for Host B


# ── REST / Local-testing helpers ──────────────────────────────────────────────


class PipelineRequest(Model):
    """Payload accepted by the Orchestrator's REST POST /process endpoint."""

    pdf_path: str = ""  # absolute or relative path to a PDF on disk
    pdf_base64: str = ""  # base64-encoded PDF bytes (alternative to path)
    user_prompt: str = "Turn this into a 3-minute debate"


class PipelineResponse(Model):
    """Response returned by the Orchestrator's REST POST /process endpoint."""

    audio_base64: str
    audio_path: str
    script_json: str  # JSON-serialised list of DialogueLine dicts
    topic_title: str
    status: str  # "success" | "error"
    error_message: str = ""
