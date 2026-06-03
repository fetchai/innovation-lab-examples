"""Drive a real Greenhouse application page with Playwright so the user can
**watch the actual form fill in real time** — both as a popup browser window
(when LIVE_FILL_MODE=headed) and as screenshots streamed into the chat.

The boards-api submission path in the submitter agent is the source of truth
for "did this actually post". This module is purely a **visual companion**:
- Loads the human-facing Greenhouse posting in Chromium.
- Locates inputs by their `name` attribute (which matches the boards-api
  field names the extractor returns), then types/selects each value with a
  small delay so the fill is visible.
- Yields screenshot bytes at meaningful milestones so the chat handler can
  stream them as `ResourceContent` images.

Design choices:
- **Async generator API**: the chat handler iterates milestones, captioning
  each one and uploading the screenshot, so the user sees progress
  interleaved with text status without this module knowing anything about
  the chat protocol.
- **Best-effort selectors**: if a field can't be found by `name=` we
  silently skip it. The screenshots show the user what got filled, which
  is the point.
- **No submit**: this module never clicks the submit button. Submission
  stays in the dedicated submitter agent via boards-api.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Locator,
    Page,
    async_playwright,
)


# Chrome on a real laptop, not a CI bot.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1280, "height": 900}


@dataclass
class FillEvent:
    """One milestone emitted by the live fill — either a screenshot to stream
    or a status line to log/render."""

    kind: str  # "started" | "field_filled" | "field_skipped" | "screenshot" | "done" | "error"
    message: str = ""
    field_name: Optional[str] = None
    value: Optional[Any] = None
    screenshot_png: Optional[bytes] = None  # set on kind="screenshot" / "done"
    error: Optional[str] = None


def _css_escape(name: str) -> str:
    """Escape a name attribute for use in a CSS selector. Greenhouse uses
    names like `urls[LinkedIn]` and `job_application[answers_attributes][12345][text_value]`
    which contain `[`, `]`, `.` that need escaping."""
    return name.replace("\\", "\\\\").replace('"', '\\"')


async def _wait_for_form(page: Page, *, timeout: int = 20000) -> bool:
    """Best-effort wait for the Greenhouse application form to render. Tries
    a few common selectors so we work across the two Greenhouse front-ends."""
    candidates = [
        '#application_form',
        'form[action*="applications"]',
        'input[name="first_name"]',
        'input[name="job_application[first_name]"]',
    ]
    for sel in candidates:
        try:
            await page.wait_for_selector(sel, state="visible", timeout=timeout // len(candidates))
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _find_input_for_name(page: Page, name: str) -> Optional[Locator]:
    """Try a list of selectors that all mean 'the form input whose
    Greenhouse-API field name is `name`'. Returns the first locator that
    resolves to a visible element."""
    escaped = _css_escape(name)
    candidates = [
        f'[name="{escaped}"]',
        f'[name="job_application[{escaped}]"]',
        f'[id="{escaped}"]',
        f'[id$="_{escaped}"]',
        # Custom-question pattern: name="question_12345" or in the job_application bracket form
        f'[name$="[{escaped}]"]',
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                # Force-visible check on the first element only
                try:
                    if await loc.is_visible(timeout=200):
                        return loc
                except Exception:  # noqa: BLE001
                    # Some elements (hidden file inputs) report not-visible but are still usable.
                    return loc
        except Exception:  # noqa: BLE001
            continue
    return None


async def _fill_one_field(
    page: Page,
    name: str,
    value: Any,
    *,
    ftype: str,
    resume_path: Optional[str] = None,
    type_delay_ms: int = 25,
) -> tuple[bool, str]:
    """Fill a single field. Returns (success, message)."""
    ftype = (ftype or "").lower()

    if ftype in {"input_file", "file"}:
        if not resume_path:
            return False, "no resume file on disk"
        # File inputs are often hidden; use a relaxed locator and direct API.
        try:
            loc = page.locator(f'input[type="file"][name="{_css_escape(name)}"]').first
            if await loc.count() == 0:
                loc = page.locator('input[type="file"]').first
            await loc.set_input_files(resume_path)
            return True, f"attached {resume_path.split('/')[-1]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"file upload failed: {exc}"

    loc = await _find_input_for_name(page, name)
    if loc is None:
        return False, "input not found on page"

    try:
        tag = await loc.evaluate("el => el.tagName.toLowerCase()")
    except Exception:  # noqa: BLE001
        tag = "input"

    try:
        await loc.scroll_into_view_if_needed(timeout=2000)
    except Exception:  # noqa: BLE001
        pass

    try:
        if tag == "select":
            # Greenhouse selects accept value OR label.
            try:
                await loc.select_option(value=str(value))
            except Exception:  # noqa: BLE001
                await loc.select_option(label=str(value))
            return True, "selected"

        if ftype in {"input_radio", "radio"} or (
            isinstance(value, str) and tag == "input"
        ):
            # Radio / checkbox: click the option with matching value.
            try:
                # Both `name` matches AND value matches → check it.
                radios = page.locator(
                    f'input[name="{_css_escape(name)}"][value="{_css_escape(str(value))}"]'
                )
                if await radios.count() > 0:
                    await radios.first.check(timeout=1500)
                    return True, "selected radio"
            except Exception:  # noqa: BLE001
                pass

        # Default: fill or type
        try:
            await loc.fill("")
        except Exception:  # noqa: BLE001
            pass

        # `type` produces visible-keystroke animation; `fill` is instant.
        # Use `type` for short values, `fill` for long ones (chat clients
        # would rather see a long answer appear at once than wait 20s).
        text_value = str(value) if not isinstance(value, list) else ", ".join(value)
        if len(text_value) <= 80:
            await loc.type(text_value, delay=type_delay_ms)
        else:
            await loc.fill(text_value)
        return True, f"typed {len(text_value)} chars"
    except Exception as exc:  # noqa: BLE001
        return False, f"interaction failed: {exc}"


async def live_fill(
    application_url: str,
    filled_fields: list[dict[str, Any]],
    *,
    resume_path: Optional[str] = None,
    headless: bool = True,
    screenshot_every_n_fields: int = 3,
    nav_timeout_ms: int = 30000,
) -> AsyncIterator[FillEvent]:
    """Open `application_url` in Chromium and walk through `filled_fields`,
    yielding `FillEvent`s as we go.

    `filled_fields` items are expected to look like the session's filled
    entries (`{name, value, source, ftype, ...}`).
    """
    pw = None
    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport=DEFAULT_VIEWPORT,
            locale="en-US",
        )
        page = await context.new_page()

        yield FillEvent(kind="started", message=f"Opening {application_url}")

        try:
            await page.goto(application_url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
        except Exception as exc:  # noqa: BLE001
            yield FillEvent(kind="error", error=f"navigation failed: {exc}")
            return

        await _wait_for_form(page)
        await asyncio.sleep(0.6)  # let any client-side hydration settle

        # Initial screenshot — show the blank form.
        try:
            shot = await page.screenshot(full_page=False, type="png")
            yield FillEvent(
                kind="screenshot",
                message="Blank form loaded",
                screenshot_png=shot,
            )
        except Exception:  # noqa: BLE001
            pass

        filled_since_shot = 0
        for f in filled_fields:
            name = f.get("name")
            value = f.get("value")
            ftype = f.get("ftype") or ""
            if not name or value in (None, ""):
                continue

            ok, detail = await _fill_one_field(
                page,
                name,
                value,
                ftype=ftype,
                resume_path=resume_path if ftype.lower() in {"input_file", "file"} else None,
            )
            if ok:
                yield FillEvent(
                    kind="field_filled",
                    field_name=name,
                    value=value,
                    message=detail,
                )
                filled_since_shot += 1
            else:
                yield FillEvent(
                    kind="field_skipped",
                    field_name=name,
                    value=value,
                    message=detail,
                )

            if filled_since_shot >= screenshot_every_n_fields:
                filled_since_shot = 0
                try:
                    shot = await page.screenshot(full_page=False, type="png")
                    yield FillEvent(
                        kind="screenshot",
                        message=f"progress after `{name}`",
                        screenshot_png=shot,
                    )
                except Exception:  # noqa: BLE001
                    pass

        # Final full-page screenshot.
        try:
            final = await page.screenshot(full_page=True, type="png")
            yield FillEvent(
                kind="done",
                message="Form complete (boards-api submit still happens on `submit live`)",
                screenshot_png=final,
            )
        except Exception:  # noqa: BLE001
            yield FillEvent(kind="done", message="Form filled")

    finally:
        # Best-effort teardown — never raise from cleanup.
        for resource in (page, context, browser):
            if resource is not None:
                try:
                    await resource.close()
                except Exception:  # noqa: BLE001
                    pass
        if pw is not None:
            try:
                await pw.stop()
            except Exception:  # noqa: BLE001
                pass
