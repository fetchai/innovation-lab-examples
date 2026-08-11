"""
Q&A Agent — main entry point.

Accepts any natural language question about hackathons and returns
a natural language answer by routing through the appropriate handler.

Usage:
    from agent.qa import ask

    answer = ask("What AI hackathons are open in San Francisco next month?")
    print(answer)

    answer = ask("Tell me about the AIEWF hackathon")
    print(answer)

    answer = ask("How many hackathons on Devpost have prizes over $10k?")
    print(answer)

Interactive CLI:
    python scripts/agent/qa.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from agent.lookup import format_event_detail, lookup_event
from agent.parse import parse_question
from agent.stats import answer_stat
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL
from recommend.engine import format_results, recommend


def ask(question: str, verbose: bool = False) -> str:
    """
    Ask any question about hackathons. Returns a natural language answer.
    """
    if verbose:
        print(f"\n[QA] Question: {question}")

    # Step 1: parse intent
    parsed = parse_question(question)
    intent = parsed.get("intent", "search")

    if verbose:
        print(f"[QA] Intent: {intent}")

    # Step 2: route to appropriate handler
    if intent == "general":
        return parsed.get("answer", "I don't have a specific answer for that.")

    elif intent == "lookup":
        event_name = parsed.get("event_name", question)
        if verbose:
            print(f"[QA] Looking up: {event_name}")
        ev = lookup_event(event_name)
        if ev:
            return format_event_detail(ev)
        return f"I couldn't find an event matching '{event_name}'. Try a more specific name."

    elif intent == "stat":
        stat_query = parsed.get("stat_query", question)
        if verbose:
            print(f"[QA] Stat query: {stat_query}")
        return answer_stat(stat_query)

    else:  # "search" (default)
        prefs = parsed.get("prefs", {})
        if not prefs:
            prefs = {"keywords": question}
        if verbose:
            print(f"[QA] Search prefs: {prefs}")

        results = recommend(prefs)
        if not results:
            return _no_results_answer(question, prefs)

        formatted = format_results(results, max_show=5)
        return _synthesise_answer(question, formatted)


def _synthesise_answer(question: str, results_text: str) -> str:
    """Wrap raw results in a friendly conversational response."""
    prompt = f"""A user asked: "{question}"

Here are the top matching hackathon events:

{results_text}

Write a friendly, concise response (3-6 sentences) that:
1. Directly answers their question
2. Highlights the top 2-3 most relevant events with key details
3. Mentions registration status and links where available
4. Ends with an offer to filter further or get more details

Don't use bullet points — write naturally."""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "temperature": 0.5,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return results_text


def _no_results_answer(question: str, prefs: dict) -> str:
    parts = []
    if prefs.get("location"):
        parts.append(f"in {prefs['location']}")
    if prefs.get("date_from"):
        parts.append(f"from {prefs['date_from']}")
    filters = " ".join(parts)
    return (
        f"I couldn't find any hackathons matching your criteria{' ' + filters if filters else ''}. "
        "Try broadening the date range, removing the location filter, or using different keywords."
    )


# ── Interactive CLI ────────────────────────────────────────────────────────


def _run_cli():
    print("\n" + "=" * 60)
    print("  Hackathon Q&A Agent")
    print("  Powered by ASI:One + 16,700+ events")
    print("  Type 'quit' to exit")
    print("=" * 60 + "\n")

    history = []

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        history.append({"role": "user", "content": question})
        answer = ask(question, verbose=True)
        print(f"\nAgent: {answer}\n")
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    _run_cli()
