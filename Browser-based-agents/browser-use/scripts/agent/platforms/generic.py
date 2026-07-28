"""
Generic registration handler using browser-use + ASI:One.

Used for: Luma, Eventbrite, Devpost, Partiful, ETHGlobal, Devfolio,
and any other platform without a dedicated handler.

browser-use drives the browser with natural language instructions.
We give it the pre-generated answers so it doesn't need to reason
about what to write — just where to put it.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from browser_use import Agent, Browser, BrowserProfile
from browser_use.llm import ChatOpenAI
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL
from agent.profile import save_profile


def _get_llm():
    """ASI:One via OpenAI-compatible interface."""
    return ChatOpenAI(
        model="asi1-mini",
        api_key=ASI_ONE_API_KEY,
        base_url=ASI_ONE_BASE_URL,
        temperature=0,
    )


BOT_CHECK_KEYWORDS = ("turnstile", "cloudflare", "verify you are human", "captcha")
BOT_CHECK_REPEAT_THRESHOLD = 3  # consecutive identical actions on a bot-check page
STUCK_ACTION_REPEAT_THRESHOLD = 3  # identical action producing literally zero DOM change
MAX_STUCK_SELECT_ROUNDS = 2  # cap how many times we'll switch-to-keyboard-nav per registration


def _make_watchdogs():
    """
    Two step-level watchdogs that stop a run stuck in an unproductive retry
    loop, so we can react to it programmatically afterward instead of relying
    on the LLM to notice and burning the whole step budget:

      - bot-check: same action repeated on a CAPTCHA/anti-bot page (e.g. MLH's
        Cloudflare Turnstile on sign-in).
      - stuck-select: same action repeated with the page's rendered text
        completely unchanged — not "wrong value selected", but literally no
        observable effect at all. Seen with Luma's custom dropdown widgets:
        the agent clicks a freshly-indexed option each time, is told by
        browser-use's own loop-detection nudge to "try something different,"
        and just... clicks again. Telling it harder in the prompt doesn't fix
        this reliably, so we detect it in code and force a real change of
        technique (keyboard navigation) on resume — see _resume_after_stuck_select.

    Returns (new_step_callback, should_stop_callback, state) — state["stopped_reason"]
    is one of "blocked_by_bot_check", "stuck_on_select", or None.
    """
    state = {
        "last_action_sig": None,
        "last_dom_text": None,
        "bot_check_repeat_count": 0,
        "stuck_repeat_count": 0,
        "stopped_reason": None,
    }

    def new_step_callback(browser_state_summary, agent_output, step_number):
        try:
            dom_text = browser_state_summary.dom_state.llm_representation()
        except Exception:
            dom_text = ""
        page_text = f"{browser_state_summary.title} {dom_text}".lower()
        is_bot_check_page = any(kw in page_text for kw in BOT_CHECK_KEYWORDS)

        action_sig = str(getattr(agent_output, "action", None))
        same_action = action_sig == state["last_action_sig"]
        same_dom = dom_text == state["last_dom_text"]

        state["bot_check_repeat_count"] = (
            state["bot_check_repeat_count"] + 1 if (is_bot_check_page and same_action) else 0
        )
        state["stuck_repeat_count"] = (
            state["stuck_repeat_count"] + 1 if (same_action and same_dom and not is_bot_check_page) else 0
        )

        state["last_action_sig"] = action_sig
        state["last_dom_text"] = dom_text

    async def should_stop_callback() -> bool:
        if state["bot_check_repeat_count"] >= BOT_CHECK_REPEAT_THRESHOLD:
            state["stopped_reason"] = "blocked_by_bot_check"
            return True
        if state["stuck_repeat_count"] >= STUCK_ACTION_REPEAT_THRESHOLD:
            state["stopped_reason"] = "stuck_on_select"
            return True
        return False

    return new_step_callback, should_stop_callback, state


async def _resume_after_stuck_select(agent) -> "AgentHistoryList":
    """
    Recover from a detected stuck-repeat loop (same action, zero visible DOM
    change, several times in a row). This covers two different situations —
    give the agent guidance for both, since the watchdog can't tell which one
    it hit:
      1. Trying to SET a value in a custom dropdown/combobox and pointer
         clicks aren't landing — switch to keyboard navigation.
      2. Trying to CLEAR/blank a field that's on the DO NOT GUESS "leave
         unknown" list, and it keeps appearing to still have content — this
         is almost always a stale element index after a re-render, not the
         page actively re-populating it, and it is NOT a reason to keep
         retrying or to treat the field as unresolvable-the-task.
    """
    agent.add_new_task(
        "Your last several attempts to interact with some field produced NO visible change to "
        "the page at all — not a wrong selection, literally nothing changed. STOP repeating "
        "that exact action — do not do it again even once more. Which of these matches what "
        "you were doing?\n\n"
        "CASE 1 — you were trying to SELECT a value in a dropdown/combobox: switch to the "
        "keyboard. Click ONCE on the field itself to focus it (not an option inside an "
        "already-open list, and not more than once), then use send_keys to press ArrowDown one "
        "or more times to move through the options — re-read the page after each press to see "
        "which option is now highlighted — and press Enter once the option you want is "
        "highlighted. If it's a searchable/typeahead combobox, you can instead type the option's "
        "name to filter to it, then press Enter.\n\n"
        "CASE 2 — you were trying to CLEAR/blank a field that belongs on your UNKNOWN "
        "(DO NOT GUESS) list, and it keeps appearing to still show content: STOP trying "
        "immediately, right now, without even one more attempt. Ask yourself: does your UNKNOWN "
        "list (including this field) have ANY entries at all? If yes — and it does, since this "
        "field is one — you are never going to submit this form, so this field's on-page value "
        "literally does not matter anymore. Do not verify it, do not retry clearing it, do not "
        "take a screenshot to check. Just note it in your FIELD_INPUT_REQUIRED report exactly as "
        "you already had it and move directly to calling done — clearing was never required for "
        "a field you're reporting as unknown, only for one you'd otherwise be about to submit "
        "with a leftover accidental value in it (which isn't your situation here).\n\n"
        "Either way: once that field is resolved (per whichever case applies), continue the "
        "original registration task exactly as instructed before. If your UNKNOWN list is empty, "
        "keep filling in anything remaining and submit once ready. If your UNKNOWN list still has "
        "one or more fields on it, do NOT click submit at all — go straight to calling done with "
        "the FIELD_INPUT_REQUIRED format from the original instructions."
    )
    return await agent.run(max_steps=_resumed_max_steps(agent))


OTP_REQUIRED_SENTINEL = "OTP_REQUIRED"
FIELD_INPUT_REQUIRED_SENTINEL = "FIELD_INPUT_REQUIRED"
REGISTRATION_CLOSED_SENTINEL = "REGISTRATION_CLOSED"
MAX_FIELD_INPUT_ROUNDS = 3  # cap how many rounds of unknown-field batches we'll stop-and-ask for
# 25 was too tight in practice: a single unreliable custom widget (e.g. a toggle
# checkbox the agent can't visually confirm) can burn the whole budget before the
# agent ever reaches FIELD_INPUT_REQUIRED, so the user never even gets asked about
# the real missing fields — see the reboot-agent-code-jul30-2026 dry run that
# needed ~30 steps just to give up on a stuck consent checkbox and report the rest.
INITIAL_STEP_BUDGET = 40
RESUME_STEP_BUDGET = 25  # extra steps granted to a resumed run (see _resumed_max_steps)


def _resumed_max_steps(agent, extra: int = RESUME_STEP_BUDGET) -> int:
    """
    `agent.run(max_steps=N)` treats `agent.state.n_steps` as a running total
    across calls on the same Agent instance rather than resetting it, so a
    resumed run (after an OTP or FIELD_INPUT_REQUIRED hand-off) must be given
    a cap ABOVE the steps already taken — reusing the original max_steps
    value here would make the loop condition `n_steps <= max_steps` false
    immediately, so the resumed run would silently do nothing.
    """
    return agent.state.n_steps + extra


async def register(
    event_url: str,
    profile,
    answers: dict[str, str],
    event_title: str = "",
    headless: bool = False,
    get_otp: "callable | None" = None,
    get_field_input: "callable | None" = None,
    profile_path: str | None = None,
    agent_address: str | None = None,
    interactive: bool = True,
) -> dict:
    """
    Use browser-use to register for any event.
    Returns {"success": bool, "message": str}, or, when interactive=False and
    the form needs info the profile doesn't have, {"success": False,
    "needs_field_input": True, "missing_fields": [...], "_resume_state": {...}}
    — see `interactive` and `resume_registration()` below.

    get_otp: optional callable (sync or async) used to obtain a one-time
    login code when the platform's sign-in genuinely requires one (e.g. MLH,
    where there's no registration form to reach without logging in first —
    unlike Luma's post-submit OTP, which is optional and never blocks
    registration). Defaults to prompting on stdin via `input()`, matching the
    existing pattern in platforms/cerebralvalley.py. Pass a callable to wire
    this up to a different input channel (e.g. a chat prompt) instead.

    get_field_input: optional callable (sync or async), called as
    get_field_input(missing_fields) -> dict[str, str], used when the form
    asks for one or more things the profile has no answer for (e.g. "T-shirt
    size", "dietary restrictions") — instead of letting the agent guess or
    burn its whole step budget retrying a selection it isn't sure about, it
    fills in everything else, stops once it's gone through the WHOLE form,
    and reports every such field at once so the human is asked for all of
    them together rather than one at a time. Only used when interactive=True
    and no `get_field_input` resume is otherwise handled by the caller;
    defaults to prompting on stdin via `input()` for each missing field.

    interactive: when True (default — used by the CLI), blocks in this same
    call to collect missing-field answers (via get_field_input/input()) and
    resumes immediately. When False (used by the chat UI, which cannot block
    a single incoming-message handler while waiting for a human's reply to a
    LATER message), this function instead returns early with
    needs_field_input=True and a "_resume_state" handle — the browser is kept
    alive (not closed) so the caller can show the human a form for all the
    missing fields at once, then call resume_registration() with the answers
    once they arrive. This never lets the agent guess-and-submit in the
    meantime, since the task instructions require it to stop BEFORE the final
    submit action whenever any field is unknown (see _build_task).
    """
    task = _build_task(event_url, profile, answers, event_title)

    # MLH and similar event pages embed many cross-origin iframes (ads, social
    # widgets, video embeds) whose DOM content otherwise gets serialized into
    # every step's prompt — this alone can blow past asi1-mini's 262k context
    # window before the agent ever takes an action. Keep same-origin iframes
    # (registration forms are often same-origin) but drop cross-origin ones.
    browser = Browser(
        browser_profile=BrowserProfile(
            headless=headless,
            cross_origin_iframes=False,
            max_iframes=10,
            # Without this, browser-use tears the session down at the end of
            # every agent.run() call (even mid-registration), so a resumed
            # run via agent.add_new_task() (used for the OTP/field hand-offs)
            # would inherit an already-dead session and fail immediately.
            keep_alive=True,
        )
    )

    new_step_callback, should_stop_callback, watchdog_state = _make_watchdogs()
    keep_browser_alive = False

    try:
        agent = Agent(
            task=task,
            llm=_get_llm(),
            browser=browser,
            max_failures=3,
            use_vision=False,
            max_clickable_elements_length=20000,
            register_new_step_callback=new_step_callback,
            register_should_stop_callback=should_stop_callback,
        )
        result = await agent.run(max_steps=INITIAL_STEP_BUDGET)

        if _is_registration_closed(result):
            return {
                "success": False,
                "registration_closed": True,
                "message": _summarize_result(result),
                "final_url": "",
            }

        if watchdog_state["stopped_reason"] == "blocked_by_bot_check":
            return {
                "success": False,
                "message": (
                    "Registration blocked by an anti-bot challenge (e.g. Cloudflare "
                    "Turnstile) on the sign-in/registration page — this cannot be "
                    "completed by an automated browser."
                ),
                "final_url": "",
            }

        for _ in range(MAX_STUCK_SELECT_ROUNDS):
            if watchdog_state["stopped_reason"] != "stuck_on_select":
                break
            watchdog_state["stopped_reason"] = None
            watchdog_state["stuck_repeat_count"] = 0
            result = await _resume_after_stuck_select(agent)

        if _needs_otp(result):
            result = await _resume_with_otp(agent, result, get_otp)

        if _needs_field_input(result):
            if interactive:
                for _ in range(MAX_FIELD_INPUT_ROUNDS):
                    if not _needs_field_input(result):
                        break
                    result = await _resume_with_field_values(agent, result, profile, get_field_input, profile_path, agent_address=agent_address)
            else:
                keep_browser_alive = True
                return {
                    "success": False,
                    "needs_field_input": True,
                    "missing_fields": _parse_field_requests(result.final_result() or ""),
                    "_resume_state": {"agent": agent, "browser": browser},
                }

        success = _check_result(result)
        return {
            "success": success,
            "already_registered": success and _detect_already_registered(result),
            "message": _summarize_result(result),
            "final_url": "",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if not keep_browser_alive:
            await browser.close()


async def resume_registration(
    resume_state: dict,
    answers: dict[str, str],
    profile,
    profile_path: str | None = None,
    agent_address: str | None = None,
) -> dict:
    """
    Continue a registration previously paused by register(interactive=False)
    with needs_field_input=True. Saves `answers` into the profile (so future
    registrations already know them), feeds them into the SAME browser
    session (resume_state — the live agent/browser from that earlier call),
    and lets the agent finish filling in and submitting the form.

    Returns the same shape as register(): either the final {"success", ...}
    result, or — if the form turns out to need yet another round of unknown
    fields — {"success": False, "needs_field_input": True, "missing_fields":
    [...], "_resume_state": {...}} again, so the caller can repeat the same
    ask-a-form-then-resume cycle.
    """
    agent = resume_state["agent"]
    browser = resume_state["browser"]
    keep_browser_alive = False

    try:
        result = await _apply_field_answers_and_resume(agent, profile, answers, profile_path, agent_address=agent_address)

        if _needs_field_input(result):
            keep_browser_alive = True
            return {
                "success": False,
                "needs_field_input": True,
                "missing_fields": _parse_field_requests(result.final_result() or ""),
                "_resume_state": {"agent": agent, "browser": browser},
            }

        success = _check_result(result)
        return {
            "success": success,
            "already_registered": success and _detect_already_registered(result),
            "message": _summarize_result(result),
            "final_url": "",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if not keep_browser_alive:
            await browser.close()


def _leading_sentinel(final_text: str) -> str:
    """
    First non-blank line of the agent's final report, uppercased.

    Sentinels are only ever matched against this leading line (not
    "anywhere in the text") because the agent's failure report can
    otherwise mention a sentinel word in passing — e.g. narrating that it
    considered FIELD_INPUT_REQUIRED for a field it actually already filled —
    which would otherwise falsely trigger a resume for an unrelated failure
    (observed with a genuine Cloudflare block: the report's prose contained
    "FIELD_INPUT_REQUIRED" even though nothing was actually missing).
    """
    for line in final_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.upper()
    return ""


def _needs_otp(result) -> bool:
    """Whether the agent stopped because a mandatory sign-in OTP blocked it."""
    if result.is_successful():
        return False
    final_text = result.final_result() or ""
    return _leading_sentinel(final_text) == OTP_REQUIRED_SENTINEL


def _is_registration_closed(result) -> bool:
    """Whether the agent stopped because the event's registration/RSVP is closed."""
    if result.is_successful():
        return False
    final_text = result.final_result() or ""
    return _leading_sentinel(final_text) == REGISTRATION_CLOSED_SENTINEL


async def _resume_with_otp(agent, result, get_otp) -> "AgentHistoryList":
    """
    Prompt for the OTP code that was emailed to the user, feed it back into
    the SAME browser session (so the sign-in flow / cookies aren't lost),
    and let the agent continue the original registration task.
    """
    print(f"\n[REGISTER] {result.final_result()}\n")

    if get_otp is not None:
        code = get_otp()
        if hasattr(code, "__await__"):
            code = await code
    else:
        code = input("[REGISTER] Enter the OTP code sent to your email: ").strip()

    digits = list(code)
    spelled_out = ", then ".join(f"'{d}'" for d in digits)

    agent.add_new_task(
        f"The user has provided the one-time verification code: {code} "
        f"(exactly {len(digits)} characters, in this order: {spelled_out}).\n\n"
        "The code is very likely split across multiple separate single-character "
        "input boxes (one box per digit) rather than a single text field. These "
        "boxes commonly re-render themselves after each keystroke (e.g. to "
        "auto-advance focus to the next box), which invalidates any other box's "
        "element reference that was found before that keystroke. So:\n"
        f"1. Type ONLY ONE digit, into ONLY ONE box, per step — never queue up "
        f"multiple type actions for different boxes in the same step. Go in "
        f"left-to-right order: {spelled_out}, box 1 through box {len(digits)}, "
        "and do not stop, pause, or double back until you have typed into ALL "
        f"{len(digits)} boxes once each.\n"
        "2. TRUST a successful input action result. If the tool reports the "
        "digit was typed successfully, treat that box as done and immediately "
        "move on to the NEXT box — do not re-read, re-verify, clear, or retype "
        "a box you just successfully typed into. The page may visually look "
        "like it is still loading/skeleton content even when your input "
        "already landed correctly — that visual appearance is NOT a sign of "
        "failure and is NOT a reason to clear or restart. Only treat a box as "
        "failed if the input action itself returns an explicit error.\n"
        "3. Do not type any letter, space, or placeholder character into any box "
        "— only the exact digit for that position.\n"
        f"4. Only after you have typed into all {len(digits)} boxes (per rules "
        "1-2 above), do exactly ONE verification pass: read the current value "
        "of each box. If a box's value doesn't match its intended digit, fix "
        "ONLY that specific box (clear it and retype the one correct digit) — "
        "never clear or retype a box that already shows the correct digit, and "
        "never restart the whole sequence from box 1.\n"
        "5. Only once all boxes show the correct code, click the Continue/Verify/"
        "Submit button. Do NOT click 'Resend' or request a new code — that "
        "invalidates this code. If you accidentally click Resend or the wrong "
        "button, stop immediately and call done with success=false explaining "
        "that the code was invalidated by mistake, rather than continuing to "
        "guess — do not retry blindly.\n\n"
        "Once sign-in is confirmed, continue the original registration task from "
        "where you left off — reach the registration/RSVP form, fill it in, "
        "submit it, and call done once you see a confirmation, exactly as "
        "instructed before."
    )

    # Force one action per LLM turn during the OTP entry so the agent is
    # compelled to re-read the page (and get fresh element references) before
    # each digit, instead of batching several type actions off one DOM
    # snapshot that a re-rendering OTP widget will invalidate mid-batch.
    original_max_actions = agent.settings.max_actions_per_step
    agent.settings.max_actions_per_step = 1
    try:
        return await agent.run(max_steps=_resumed_max_steps(agent))
    finally:
        agent.settings.max_actions_per_step = original_max_actions


def _needs_field_input(result) -> bool:
    """Whether the agent stopped because a form field asked for something the profile doesn't have."""
    if result.is_successful():
        return False
    final_text = result.final_result() or ""
    return _leading_sentinel(final_text) == FIELD_INPUT_REQUIRED_SENTINEL


def _parse_field_requests(final_text: str) -> list[dict]:
    """
    Parse the agent's FIELD_INPUT_REQUIRED report into a list of
    {"field_name", "options", "note"} dicts — one per unknown field found
    across the WHOLE form (see the FIELD_INPUT_REQUIRED instructions in
    _build_task for the exact JSON-array wire format expected).
    """
    body = "\n".join(final_text.splitlines()[1:]).strip()
    # The model doesn't reliably keep its response to JUST the sentinel +
    # JSON array as instructed — it sometimes appends trailing prose after
    # the array (e.g. "Filled MATCHED fields: ..."). Extract just the array
    # itself (first '[' through its bracket-matched ']') instead of assuming
    # the whole remaining body is valid JSON, which fails outright on any
    # trailing text and silently drops every field.
    start = body.find("[")
    if start == -1:
        return []
    depth = 0
    end = None
    for i, ch in enumerate(body[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return []
    try:
        parsed = json.loads(body[start:end + 1])
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    fields = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        options = item.get("options") or []
        if not isinstance(options, list):
            options = []
        fields.append({
            "field_name": str(item.get("field_name") or "unknown_field"),
            "options": [str(o) for o in options],
            "note": str(item.get("note") or ""),
        })
    return fields


async def _apply_field_answers_and_resume(agent, profile, answers: dict[str, str], profile_path, agent_address: str | None = None) -> "AgentHistoryList":
    """
    Save human-provided field answers into the profile (so future
    registrations never have to ask again), then feed them all into the SAME
    browser session in one go and let the agent finish the form.
    """
    _BOOL_FIELDS = {"looking_for_job", "needs_visa"}
    for field_name, value in answers.items():
        if not value:
            continue
        if field_name in _BOOL_FIELDS:
            setattr(profile, field_name, value.strip().lower() in ("yes", "true", "y"))
        elif hasattr(profile, field_name):
            setattr(profile, field_name, value)
        else:
            profile.custom_fields[field_name] = value
    save_profile(profile, profile_path, agent_address=agent_address)

    filled = {k: v for k, v in answers.items() if v}
    summary = "; ".join(f"'{k}': '{v}'" for k, v in filled.items())
    agent.add_new_task(
        f"STOP whatever you were doing before this message — it is no longer your priority. "
        f"The user has now provided the following field values that were previously unknown: "
        f"{summary}. Filling these in is now your FIRST priority, before anything else, "
        "including any field you were stuck on earlier.\n\n"
        "1. Find each of those exact form fields and fill them in / select them now — if a field "
        "is a dropdown or custom select widget, click to open it and click the matching option "
        "(match the option text exactly). Many of these widgets TOGGLE their selection — before "
        "clicking an option, first check whether it's already shown as selected; if so, clicking "
        "it again will DESELECT it, so leave it alone.\n"
        "2. THEN, and only then, return to the original registration task: if there is any OTHER "
        "field you were stuck on before this message (e.g. one that kept failing to update no "
        "matter how many times or which method you tried), do NOT resume retrying it the same "
        "way. If a fresh, genuinely different attempt (e.g. clicking directly instead of via "
        "JavaScript, or vice versa) also doesn't work, treat that field as unfillable, leave it as "
        "whatever value it currently holds (even if blank or wrong), and move on — do not spend "
        "more than one more attempt on it. Getting the form submitted matters far more than that "
        "one field being perfect.\n"
        "3. IMPORTANT — check your ORIGINAL survey from before this message for any field you had "
        "correctly identified as UNKNOWN per the DO NOT GUESS rule that is NOT one of the field "
        "values given above. These fields were deliberately left unresolved on purpose (not every "
        "unknown field necessarily gets an answer in this round) — the DO NOT GUESS rule still "
        "applies to them exactly as before: do not fill them in, do not invent a value, do not "
        "submit the form.\n"
        "   - If ANY such field remains: do NOT click submit. Call done with success=false, with "
        f"your ENTIRE response formatted EXACTLY as before: the sentinel line "
        f"\"{FIELD_INPUT_REQUIRED_SENTINEL}\" followed by a JSON array — and re-list each such "
        "field using the SAME real field_name, options, and note text you found for it during your "
        "original survey (never an empty or placeholder entry — if you can't recall a field's "
        "exact details, re-read the form to find it again rather than submitting a blank entry).\n"
        "   - Only if NO such fields remain (every field you'd ever flagged as unknown now has a "
        "real value, either from this message or already filled before): fill in anything trivial "
        "still remaining, submit the form, and call done once you see a confirmation, exactly as "
        "instructed before."
    )

    return await agent.run(max_steps=_resumed_max_steps(agent))


async def _resume_with_field_values(agent, result, profile, get_field_input, profile_path, agent_address: str | None = None) -> "AgentHistoryList":
    """
    Ask a human for every value the profile has no answer for (e.g. T-shirt
    size, dietary restrictions) — all at once, not one at a time — then apply
    them and resume the SAME browser session. Used by the interactive
    (blocking, CLI) path; see resume_registration() for the non-blocking
    (chat) equivalent.
    """
    final_text = result.final_result() or ""
    missing = _parse_field_requests(final_text)

    print(f"\n[REGISTER] Need input for {len(missing)} field(s):")
    for m in missing:
        opts = f" ({', '.join(m['options'])})" if m["options"] else ""
        print(f"  - {m['field_name']}{opts}" + (f" — {m['note']}" if m["note"] else ""))

    if get_field_input is not None:
        answers = get_field_input(missing)
        if hasattr(answers, "__await__"):
            answers = await answers
    else:
        answers = {}
        for m in missing:
            prompt = f"[REGISTER] Enter a value for '{m['field_name']}'"
            prompt += f" ({', '.join(m['options'])}): " if m["options"] else ": "
            answers[m["field_name"]] = input(prompt).strip()

    return await _apply_field_answers_and_resume(agent, profile, answers, profile_path, agent_address=agent_address)


def _build_task(
    event_url: str,
    profile,
    answers: dict[str, str],
    event_title: str,
) -> str:
    """Build the natural language task for browser-use."""

    # Format answers as a numbered list
    answers_text = "\n".join(
        f"  - If asked '{q}': answer with '{a}'"
        for q, a in answers.items()
        if a
    )

    # Build standard field mappings
    standard = f"""
Standard fields to fill:
  - Name / Full name: {profile.full_name()}
  - First name: {profile.first_name}
  - Last name: {profile.last_name}
  - Email: {profile.email}
  - LinkedIn: {profile.linkedin_url}
  - GitHub: {profile.github_url}
  - Twitter / X: {profile.twitter_handle}
  - Location / City: {profile.location_str()}
  - Company / employer / organization: {profile.company_or_school or '(not known — see the DO NOT GUESS rule below)'}
  - Role / title: {profile.role or '(not known — see the DO NOT GUESS rule below)'}
  - T-shirt size: {profile.tshirt_size or '(not known — see the DO NOT GUESS rule below)'}
"""
    if profile.custom_fields:
        standard += "  - " + "\n  - ".join(
            f"{k}: {v}" for k, v in profile.custom_fields.items() if v
        ) + "\n"

    task = f"""Register for the hackathon "{event_title}" at {event_url}.

{standard}
{f'Custom question answers:{chr(10)}{answers_text}' if answers_text else ''}

RULE — DO NOT GUESS. This is a hard per-field checklist, not a short list of exceptions —
apply it to EVERY field on the form, one at a time, before you type or select anything:

  Does this field have a WORD-FOR-WORD match above — either (a) a "Standard fields" entry with
  an actual value (not the "(not known...)" placeholder), or (b) an exact question match in
  "Custom question answers"?
    - YES → type/select exactly that value.
    - NO  → leave it BLANK/unselected. Note down its exact visible label + options. Move on.
      There is no third option. Do not invent, infer, derive, or improvise a value for it no
      matter how plausible it seems, and no matter whether it's marked required. Concretely
      forbidden: guessing a company/employer from an email domain, guessing a project
      description from the event's theme or your read of the event, guessing dietary/allergy/
      pronoun/gender/phone/emergency-contact/T-shirt-size answers, guessing job-seeking or visa
      status from role/location, picking one side of a solo/group, yes/no, or any other
      few-option choice just because it seems like a common/default/harmless pick. A field
      having only 2-3 options, or seeming low-stakes, is NOT permission to guess between them —
      the checklist above is the ONLY thing that grants permission to fill a field, and "picking
      the first/most common/most harmless-looking option" is exactly the kind of guess this rule
      forbids. "Sounds reasonable" is never a reason to fill a field in.

This rule applies to every question the form asks, full stop — it OVERRIDES anything below
that could be read as license to improvise (there is no such license).

Instructions:
1. Go to {event_url}
1a. CHECK FOR CLOSED REGISTRATION FIRST, before trying anything else: look at the page (and,
    if there's a register/apply/RSVP/"Request to Join" button, its current text and whether it's
    disabled/greyed out) for any indication that registration is no longer open — e.g. the button
    itself says "Registration Closed", "Applications Closed", "Sold Out", "Closed", "No longer
    accepting responses", "Event has ended", is disabled/unclickable, or the page has replacement
    text to that effect instead of a live registration form. If you see this, STOP immediately —
    do not click around looking for another way in, do not try scrolling for a hidden form, do
    not treat it as a login wall or a loading state. Call done with success=false right away, with
    your ENTIRE response formatted EXACTLY as:
      {REGISTRATION_CLOSED_SENTINEL}
      <one line stating exactly what the page/button said, e.g. "Button reads 'Registration
      Closed'.">
    Only proceed to step 2 if you do NOT see any such indication.
2. If a sign-in wall blocks you from even reaching the registration/RSVP form, sign in
   with {profile.luma_email or profile.email}
3. Find and click the registration/apply/RSVP/"Request to Join" button. If clicking it (or
   anything after) reveals a closed/no-longer-accepting-responses state you couldn't see before
   (this can happen even when step 1a's check looked clear), apply step 1a's protocol right then
   instead of continuing.
4. SURVEY FIRST, FILL SECOND: before typing or selecting anything, READ ONLY — look at the
   form and sort every visible field into exactly one of two lists — MATCHED (a word-for-word
   Standard field with a real value, or an exact Custom question answer) or UNKNOWN (everything
   else, per the DO NOT GUESS checklist above). Write this classification down in your
   memory/reasoning before your first action on the form. The survey step involves ZERO clicks,
   types, or clears — it is purely reading what's already on the page. A freshly-loaded form's
   fields start empty; that is their correct, already-desired state for anything on your UNKNOWN
   list, so there is nothing to reset or clear before you've even started. If a field looks like
   it already has unexpected content before you've touched it, that's real information to note,
   not a cue to defensively clear things "to be safe."
5. Fill in ONLY the fields on your MATCHED list, one at a time, moving straight from survey to
   filling — don't clear anything first. Do NOT type into, select an option for, or otherwise
   touch any field on the UNKNOWN list — not a blank string, not "N/A", not even a defensive
   clear "just in case." For each UNKNOWN field, just note its exact visible label + options and
   leave it completely untouched — untouched means untouched, not "touched once to clear it."
6. If you realize AFTER typing that a field you filled actually belongs on the UNKNOWN list
   (a mistake): whether you need to clear it depends on what happens next, so check that first —
     - If this means your UNKNOWN list now has ANY entries at all (this one or any other), you
       are going to call done with FIELD_INPUT_REQUIRED per step 9 and never touch submit. In
       that case the field's on-page value doesn't matter anymore — do NOT spend any actions
       trying to clear it, do NOT try to verify it looks blank, just add it to your UNKNOWN
       notes as-is and move on immediately. Clearing it is pure wasted effort when nothing is
       ever going to be submitted.
     - ONLY if fixing this one mistake would make your UNKNOWN list completely empty (i.e. every
       other field is genuinely MATCHED and you are actually about to submit) is it worth
       clearing: in that case, ONE plain input action with text="" and clear=True, do NOT use
       JavaScript/`evaluate` (it has previously wiped out other correctly-filled fields as
       collateral damage), and do not loop trying to re-verify it worked — one attempt, then move
       on regardless of how it looks, since a value that shouldn't be there is still better than
       burning your whole step budget confirming it.
7. For any checkbox asking to agree to terms or conditions, check it
8. THE MOMENT your UNKNOWN list has one or more entries, the submit/"Request to Join"/apply
   button is off-limits for the REST of this task — do not activate it, not even once, not even
   "to see if it's really required" or "to check what validation error shows." This means by ANY
   method: the click action on it, a JS `evaluate` call that does `.click()` or `.submit()` on
   it or its form, dispatching a synthetic click/submit event, pressing Enter/Space while it's
   focused, or any other way of triggering it — there is no technique that is exempt just
   because it isn't literally the click action. Activating it by ANY means is still the exact
   guess-about-how-the-form-will-react and exact silent-submission risk this rule exists to
   prevent, and it wastes steps you don't have to spare. There is nothing left to discover by
   triggering it — skip straight to calling done per step 9 below instead of touching it at all,
   by any method.
9. Once you've gone through every remaining field on the form and are ready to submit, check
   whether you noted any fields under the DO NOT GUESS rule above:
   - If you noted ONE OR MORE such fields: do NOT click submit/"Request to Join"/apply — not
     even once, per step 8 above. Stop here and call done with success=false immediately, with
     your ENTIRE response formatted EXACTLY as:
       {FIELD_INPUT_REQUIRED_SENTINEL}
       <a single JSON array on the following line(s), nothing else, one entry per field, e.g.:
       [{{"field_name": "tshirt_size", "options": ["XS","S","M","L","XL"], "note": "shown after affiliation"}}]>
     Use the exact visible option text in "options" for a dropdown/select field, or an empty
     list [] for free text. Include every field you noted, not just the first one.
   - If you noted NO such fields, proceed to step 10 and submit normally.
10. Submit the form

Registration is COMPLETE as soon as you see any confirmation that the submission went
through — e.g. "You're in", "Request sent", "Registered", "Pending approval/host review",
"You have already registered"/"You're already registered"/"already RSVP'd"/"already signed
up", a confirmation modal, toast, or a redirect away from the form. As soon as you see any
of these, call done with success=true immediately — do not do anything else. If the
confirmation is specifically the "already registered/already RSVP'd/already signed up"
variety (i.e. this person had already registered before you did anything, as opposed to a
brand new submission just now going through), the word "already" MUST appear somewhere in
your done() response text — this distinction matters downstream, so don't paraphrase it away.

IMPORTANT: If a submit/join button click doesn't seem to visibly react, do NOT assume it
failed and click it again. First re-read the current page/modal text for any of the
confirmation phrases above — clicks can take a moment to register, and re-clicking a form
that already submitted can trigger duplicate-submission or verification popups. Only retry
the click if there is no confirmation text AND no popup/overlay is present.

IMPORTANT: Many custom dropdown/select/checkbox widgets (e.g. Luma's T-shirt size and dietary
restrictions fields) TOGGLE their selection — clicking an option that is ALREADY selected
DESELECTS it again, undoing correct state. Before clicking any option in such a widget, first
check the current page state for whether that option is already shown as selected/highlighted/
checked/the current field value. If it already shows the value you want, DO NOT CLICK IT
AGAIN — leave it alone and move on to the next field. Only click an option that is not yet
selected. If you're ever unsure whether a click landed, re-read the current state before
clicking that same widget again — never click a widget "just to double check" or "to be safe."

IMPORTANT: This applies to ANY field, not just dropdowns — HARD CAP: 3 total attempts on the
exact same element, no exceptions. Count every action targeting that specific element — click,
type, JS-evaluate, all of it counts toward the SAME running total, not a separate count per
method. State the running count explicitly in your memory each time you act on it ("attempt
2/3 on this element"). The instant the count reaches 3 without the change you wanted actually
sticking, STOP touching that element completely — do not take a 4th action on it under any
circumstances, even if you've just thought of a method you haven't tried yet, even if you're
sure this next one will work. Trying a 4th, 5th, 6th... time is exactly the failure this cap
exists to prevent, and "I have a new idea" is not an exemption from a hard cap.
Once you've hit the cap on a field:
  - This is a UI interaction problem, not a missing-information problem, so do NOT use the
    FIELD_INPUT_REQUIRED protocol for it — you already know the intended value, the widget is
    just unreliable.
  - If the field is optional or not obviously required, leave it as-is (blank, or whatever it
    currently holds) and move on to the rest of the form.
  - If it's a genuinely required field blocking submission (this includes a stuck "I agree to
    terms" checkbox — being unable to confirm it's checked means you can't confirm the form is
    submittable, so treat it as blocking): call done with success=false immediately and briefly
    report which field is stuck and what you were trying to do, rather than spending the rest of
    your step budget on it. Do not attempt to submit anyway "to see what happens" — that's
    covered by the separate submit-button rule above and applies here too.

IMPORTANT: Some platforms (e.g. Luma) show an OPTIONAL "verify your email to manage your
registration" sign-in/one-time-code prompt AFTER the registration is already submitted.
This step is NOT required to complete registration — it only unlocks managing/viewing the
RSVP later, and you have no way to read the verification code from the user's inbox. If
this prompt appears after you've already submitted the form, ignore/dismiss it and call
done with success=true immediately — do NOT guess or attempt to enter a verification code,
and do NOT treat an unresolved sign-in/OTP prompt as a failure.

IMPORTANT: Some platforms (e.g. MLH) instead require signing in BEFORE you can reach the
registration form at all, and that sign-in sends a one-time code to the user's email. This
is a genuine, mandatory blocker — you cannot fill it in yourself and must NOT guess a code.
If you hit this situation, call done with success=false and make the exact string
"{OTP_REQUIRED_SENTINEL}" the first line of your response, followed by which email address
the code was sent to and what step you had reached. Do not retry the sign-in more than once
after the code is sent — report the blocker immediately.

Do NOT proceed if the event requires payment — stop and report that.
Do NOT fill in credit card or payment information.
"""
    return task



ALREADY_REGISTERED_PHRASES = (
    "already registered",
    "already rsvp",
    "already signed up",
    "already applied",
    "already joined",
)


def _detect_already_registered(result) -> bool:
    """
    Distinguish "this person was already registered before now" (Luma etc.
    showing e.g. "You have already registered" instead of a fresh
    confirmation) from a brand new successful submission. Both count as
    success=True, but a caller (chat UI, CLI) usually wants to say something
    different in each case rather than implying a registration just happened.
    """
    text = (result.final_result() or "").lower()
    return any(phrase in text for phrase in ALREADY_REGISTERED_PHRASES)


def _summarize_result(result) -> str:
    """
    Human-readable one-liner for chat/CLI display. `str(result)` on a
    browser-use AgentHistoryList is a raw repr of internal ActionResult
    objects (is_done=, success=None, long_term_memory=...) — useful for our
    own debugging, not something a user should ever see. The agent's own
    final_result() is the natural-language text it wrote for its done() call,
    which is what a human actually wants to read.
    """
    text = (result.final_result() or "").strip()
    if not text:
        return "No confirmation message was captured."

    # Strip our own internal protocol sentinel lines if one ever leaks
    # through here instead of being caught upstream (e.g. FIELD_INPUT_REQUIRED).
    sentinels = {OTP_REQUIRED_SENTINEL, FIELD_INPUT_REQUIRED_SENTINEL, REGISTRATION_CLOSED_SENTINEL}
    lines = [line for line in text.splitlines() if line.strip().upper() not in sentinels]
    cleaned = "\n".join(lines).strip() or text

    return cleaned[:400]


def _check_result(result) -> bool:
    """
    Check if browser-use completed successfully.

    Prefer the agent's own explicit success/failure call to `done` — it has
    direct access to the actual page state (e.g. an "already registered"
    confirmation) and our task instructions tell it exactly what counts as
    done. The judge model only sees the trajectory after the fact and scores
    it against literal instruction-following (every optional field filled,
    every question answered) rather than whether the registration itself
    went through, which produces false negatives on real successes (verified
    against this exact event: the agent correctly called done(success=True)
    after seeing "You have already registered", but the judge failed it for
    skipping the GitHub/Location fields).
    """
    successful = result.is_successful()
    if successful is not None:
        return successful

    # Agent never called `done` (e.g. the bot-check watchdog stopped it) —
    # fall back to the judge's verdict if one was produced.
    validated = result.is_validated()
    if validated is not None:
        return validated

    # Last resort: neither produced a verdict.
    result_str = str(result).lower()
    failure_signals = ["failed", "error", "could not", "unable", "payment required"]
    success_signals = ["success", "registered", "submitted", "confirmed", "applied", "rsvp"]

    if any(s in result_str for s in failure_signals):
        return False
    if any(s in result_str for s in success_signals):
        return True
    return True  # assume success if no explicit failure
