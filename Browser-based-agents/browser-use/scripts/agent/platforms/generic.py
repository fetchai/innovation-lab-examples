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
    Recover from a detected stuck-select loop by switching the agent from
    clicking to keyboard navigation, which tends to work against custom
    combobox/listbox widgets even when pointer clicks silently don't land.
    """
    agent.add_new_task(
        "Your last several attempts to interact with some field produced NO visible change to "
        "the page at all — not a wrong selection, literally nothing changed. Clicking is not "
        "working for that specific widget. STOP clicking on it entirely — do not click it again "
        "even once more.\n\n"
        "Instead, use the keyboard: click ONCE on the field itself to focus it (not on an option "
        "inside an already-open list, and not more than once), then use send_keys to press "
        "ArrowDown one or more times to move through the options — re-read the page after each "
        "press to see which option is now highlighted/focused — and press Enter once the option "
        "you want is highlighted. If the field is a searchable/typeahead combobox, you can "
        "instead type the option's name to filter to it, then press Enter.\n\n"
        "Once that field is correctly set, continue the original registration task exactly as "
        "instructed before — fill in anything remaining, submit the form, and call done once "
        "you see a confirmation."
    )
    return await agent.run(max_steps=_resumed_max_steps(agent))


OTP_REQUIRED_SENTINEL = "OTP_REQUIRED"
FIELD_INPUT_REQUIRED_SENTINEL = "FIELD_INPUT_REQUIRED"
MAX_FIELD_INPUT_ROUNDS = 3  # cap how many rounds of unknown-field batches we'll stop-and-ask for
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
        result = await agent.run(max_steps=25)

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
    try:
        parsed = json.loads(body)
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
    for field_name, value in answers.items():
        if not value:
            continue
        if hasattr(profile, field_name):
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
        "3. Fill in any remaining fields, submit the form, and call done once you see a "
        "confirmation, exactly as instructed before."
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
  - T-shirt size: {profile.tshirt_size or '(not known — see the NEVER GUESS rule below)'}
"""
    if profile.custom_fields:
        standard += "  - " + "\n  - ".join(
            f"{k}: {v}" for k, v in profile.custom_fields.items() if v
        ) + "\n"

    task = f"""Register for the hackathon "{event_title}" at {event_url}.

{standard}
{f'Custom question answers:{chr(10)}{answers_text}' if answers_text else ''}

RULE — NEVER GUESS THESE FIELDS (read this before you fill in anything):
If the form asks for T-shirt/apparel size, dietary restrictions/food preference, allergies,
pronouns, gender, phone number, emergency contact, or any other specific personal fact/
preference that is NOT derivable from the "Standard fields" above and NOT something you can
reasonably infer from role/skills/bio — you must NOT fill it in, guess a value, or pick a
default option "just to move on." This applies even if the field is marked required. Instead:
leave that field blank/unselected, note down its name + visible options, and continue to the
rest of the form as normal (do not stop). There may be more than one such field — note ALL of
them as you go. This rule OVERRIDES step 6 below wherever the two would conflict.

Instructions:
1. Go to {event_url}
2. If a sign-in wall blocks you from even reaching the registration/RSVP form, sign in
   with {profile.luma_email or profile.email}
3. Find and click the registration/apply/RSVP/"Request to Join" button
4. Fill in all form fields using the information above — EXCEPT any field covered by the
   NEVER GUESS rule above, which you must leave alone and note down instead.
5. For any checkbox asking to agree to terms or conditions, check it
6. For any remaining question not listed above and not covered by the NEVER GUESS rule, give
   a reasonable answer based on:
   - Role: {profile.role}
   - Skills: {', '.join(profile.skills[:5])}
   - Bio: {profile.bio[:200] if profile.bio else 'Software engineer interested in AI'}
7. Once you've gone through every remaining field on the form and are ready to submit, check
   whether you noted any fields under the NEVER GUESS rule above:
   - If you noted ONE OR MORE such fields: do NOT click submit/"Request to Join"/apply. Stop
     here and call done with success=false, with your ENTIRE response formatted EXACTLY as:
       {FIELD_INPUT_REQUIRED_SENTINEL}
       <a single JSON array on the following line(s), nothing else, one entry per field, e.g.:
       [{{"field_name": "tshirt_size", "options": ["XS","S","M","L","XL"], "note": "shown after affiliation"}}]>
     Use the exact visible option text in "options" for a dropdown/select field, or an empty
     list [] for free text. Include every field you noted, not just the first one.
   - If you noted NO such fields, proceed to step 8 and submit normally.
8. Submit the form

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

IMPORTANT: This applies to ANY field, not just dropdowns — if an action on a specific field
(click, type, or JS-evaluate) does not produce the change you wanted after 2 attempts using
DIFFERENT approaches (e.g. plain click then JS-evaluate, or type then JS-evaluate), STOP
attempting that field. Do not repeat the exact same action a 3rd, 4th, 5th... time hoping it
works — if it silently failed twice with different methods, it will keep silently failing.
This is a UI interaction problem, not a missing-information problem, so do NOT use the
FIELD_INPUT_REQUIRED protocol for it — you already know the intended value. If the field is
optional or not obviously required, leave it as-is (blank or whatever it currently holds) and
move on to the rest of the form. If it's a genuinely required field blocking submission,
call done with success=false and briefly report which field is stuck and what value you were
trying to enter, rather than spending the rest of your step budget on it.

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
    sentinels = {OTP_REQUIRED_SENTINEL, FIELD_INPUT_REQUIRED_SENTINEL}
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
