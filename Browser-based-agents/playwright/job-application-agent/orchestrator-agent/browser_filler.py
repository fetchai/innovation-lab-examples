"""Drive a real Greenhouse application page with Playwright and **keep the
browser open** for the duration of the user's session so they can:

1. Watch the initial fill happen field-by-field (visible Chromium window
   when LIVE_FILL_MODE=headed, screenshots streamed into chat either way).
2. Continue to see / interact with the form after the initial fill.
3. See their chat edits reflected in the live browser in real time.

The session object is owned by `agent.py` and stays alive between chat
turns. `close()` is only called when the user submits, cancels, or pastes
a new Greenhouse URL.

The boards-api submitter agent still owns the actual submission. This
module is purely the visual + interactive layer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, AsyncIterator, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    async_playwright,
)

from options import match_option


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1280, "height": 900}


@dataclass
class FillEvent:
    """One milestone emitted by the live fill — text status or a screenshot
    to stream into chat."""

    kind: str  # "started" | "field_filled" | "field_skipped" | "screenshot" | "done" | "error"
    message: str = ""
    field_name: Optional[str] = None
    value: Optional[Any] = None
    screenshot_png: Optional[bytes] = None
    error: Optional[str] = None


def _css_escape(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _option(label: str) -> dict[str, str]:
    return {"label": label, "value": label}


DEMOGRAPHIC_OPTIONS: dict[str, list[dict[str, str]]] = {
    "gender_identity": [
        _option("Cisgender woman"),
        _option("Cisgender man"),
        _option("Transgender woman"),
        _option("Transgender man"),
        _option("Non-binary"),
        _option("Two-spirit"),
        _option("My gender identity is not listed"),
        _option("I don't wish to answer"),
    ],
    "race_ethnicity": [
        _option("American Indian or Alaskan Native"),
        _option("Black or African American"),
        _option("East Asian"),
        _option("Hispanic or Latino"),
        _option("Middle Eastern or North African"),
        _option("Native Hawaiian or Other Pacific Islander"),
        _option("South Asian"),
        _option("Southeast Asian"),
        _option("White"),
        _option("Two or More Races"),
        _option("I don't wish to answer"),
    ],
    "military_status": [
        _option("I am on active duty"),
        _option("I am part of the national guard or on reserve"),
        _option("I have never served in the military"),
        _option("I identify as a protected veteran"),
        _option("I identify as a non-protected veteran"),
        _option("I identify in multiple military status categories"),
        _option("I don't wish to answer"),
    ],
    "disability_status": [
        _option("Yes, I have a disability"),
        _option("No, I don't have a disability"),
        _option("I don't wish to answer"),
    ],
    "transgender_experience": [
        _option("Yes"),
        _option("No"),
        _option("I don't wish to answer"),
    ],
    "sexual_orientation": [
        _option("Heterosexual / Straight"),
        _option("Gay or Lesbian"),
        _option("Bisexual"),
        _option("Pansexual"),
        _option("Asexual"),
        _option("Queer"),
        _option("I use a different term"),
        _option("I don't wish to answer"),
    ],
    "lgbtq": [
        _option("Yes"),
        _option("No"),
        _option("Questioning"),
        _option("I don't wish to answer"),
    ],
}


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").replace("*", " ")).strip()


def _decline_if_requested(value: Any, options: list[dict[str, str]]) -> Optional[str]:
    normed = _norm(value)
    if normed in {
        "decline",
        "decline to answer",
        "prefer not to say",
        "i don't wish to answer",
        "do not wish to answer",
    }:
        return "I don't wish to answer"
    return None


def _exact_option(value: Any, options: list[dict[str, str]]) -> Optional[str]:
    normed = _norm(value)
    for opt in options:
        label = opt.get("label") or opt.get("value") or ""
        if _norm(label) == normed:
            return label
    return None


def _map_gender_identity(value: Any) -> Optional[str]:
    options = DEMOGRAPHIC_OPTIONS["gender_identity"]
    mapped = _decline_if_requested(value, options)
    if mapped:
        return mapped
    exact = _exact_option(value, options)
    if exact:
        return exact
    normed = _norm(value)
    if normed in {
        "male",
        "man",
        "cis male",
        "cisgender male",
        "cis man",
        "cisgender man",
    }:
        return "Cisgender man"
    if normed in {
        "female",
        "woman",
        "cis female",
        "cisgender female",
        "cis woman",
        "cisgender woman",
    }:
        return "Cisgender woman"
    if "non-binary" in normed or "nonbinary" in normed:
        return "Non-binary"
    if "transgender woman" in normed or normed == "trans woman":
        return "Transgender woman"
    if "transgender man" in normed or normed == "trans man":
        return "Transgender man"
    return None


def _map_race_ethnicity(value: Any) -> Optional[str]:
    options = DEMOGRAPHIC_OPTIONS["race_ethnicity"]
    mapped = _decline_if_requested(value, options)
    if mapped:
        return mapped
    exact = _exact_option(value, options)
    if exact:
        return exact
    normed = _norm(value)
    # "Asian" alone is ambiguous on Robinhood's split East/South/Southeast list.
    if normed == "asian":
        return None
    aliases = {
        "black": "Black or African American",
        "african american": "Black or African American",
        "hispanic": "Hispanic or Latino",
        "latino": "Hispanic or Latino",
        "latina": "Hispanic or Latino",
        "middle eastern": "Middle Eastern or North African",
        "north african": "Middle Eastern or North African",
        "native hawaiian": "Native Hawaiian or Other Pacific Islander",
        "pacific islander": "Native Hawaiian or Other Pacific Islander",
        "two or more races": "Two or More Races",
        "two or more": "Two or More Races",
    }
    if normed in aliases:
        return aliases[normed]
    return None


def _map_military_status(value: Any) -> Optional[str]:
    options = DEMOGRAPHIC_OPTIONS["military_status"]
    mapped = _decline_if_requested(value, options)
    if mapped:
        return mapped
    exact = _exact_option(value, options)
    if exact:
        return exact
    normed = _norm(value)
    if "never served" in normed:
        return "I have never served in the military"
    if "active duty" in normed:
        return "I am on active duty"
    if "national guard" in normed or "reserve" in normed:
        return "I am part of the national guard or on reserve"
    if "non-protected veteran" in normed:
        return "I identify as a non-protected veteran"
    if "protected veteran" in normed and "not" not in normed:
        return "I identify as a protected veteran"
    # "I am not a protected veteran" — the "not" guard above rejects it, so
    # return the phrase verbatim; option-snapping in discover_profile_fillables
    # will match it against whatever the live form actually uses.
    if "not" in normed and "veteran" in normed:
        return value if isinstance(value, str) else str(value)
    return None


def _map_disability_status(value: Any) -> Optional[str]:
    options = DEMOGRAPHIC_OPTIONS["disability_status"]
    mapped = _decline_if_requested(value, options)
    if mapped:
        return mapped
    exact = _exact_option(value, options)
    if exact:
        return exact
    normed = _norm(value)
    if normed in {"yes", "true", "1", "disabled", "i have a disability"}:
        return "Yes, I have a disability"
    if normed in {
        "no",
        "false",
        "0",
        "none",
        "not disabled",
        "i do not have a disability",
    }:
        return "No, I don't have a disability"
    return None


_US_STATES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
    "PR",
    "GU",
    "VI",
    "AS",
    "MP",
}


def _profile_value_for_live_label(
    profile: dict[str, Any], label: str, *, ftype: str
) -> tuple[Optional[str], Optional[str], list[dict[str, str]]]:
    normed = _norm(label)

    # Country — infer "United States" from US state when country not explicit
    if "country" in normed and ftype in {"multi_value_single_select", "input_text"}:
        country = profile.get("country")
        if not country:
            state = (profile.get("state") or "").strip().upper()
            if state in _US_STATES:
                country = "United States"
        if country:
            return "country", country, []

    # City / location
    if (
        "city" in normed or normed == "location" or normed.startswith("location ")
    ) and ftype == "input_text":
        city = profile.get("city")
        if city:
            return "city", city, []

    # EEO / demographic fields
    # -------------------------------------------------------------------
    # Greenhouse uses React comboboxes for these — the JS in
    # discover_profile_fillables can't extract their options at rest, so
    # control.get("options") is always [].  The actual fill goes through
    # _select_styled_dropdown which opens the live dropdown and does
    # substring matching against the real [role="option"] text.
    # We therefore pass the RAW profile value (e.g. "Male", "No",
    # "I am not a protected veteran") so the substring match finds the
    # right live option instead of a hardcoded label that may not exist.
    if "gender" in normed and "transgender" not in normed:
        return "gender", profile.get("gender"), []
    if "transgender" in normed:
        return "transgender_experience", profile.get("transgender_experience"), []
    if "sexual orientation" in normed:
        return "sexual_orientation", profile.get("sexual_orientation"), []
    # "Are you Hispanic or Latino?" — derive Yes/No from stored race_ethnicity.
    if "hispanic" in normed or "latino" in normed:
        re_val = _norm(profile.get("race_ethnicity") or "")
        if "hispanic" in re_val or "latino" in re_val or "latina" in re_val:
            derived: Optional[str] = "Yes"
        elif re_val:
            derived = "No"
        else:
            derived = None
        return "race_ethnicity", derived, []
    if (
        "race or ethnicity" in normed
        or "race/ethnicity" in normed
        or (
            "ethnicity" in normed
            and "hispanic" not in normed
            and "latino" not in normed
        )
    ):
        return "race_ethnicity", profile.get("race_ethnicity"), []
    if "military status" in normed or "veteran" in normed:
        return "veteran_status", profile.get("veteran_status"), []
    if "disability status" in normed:
        return "disability_status", profile.get("disability_status"), []
    if "lgbtq" in normed:
        extras = profile.get("extras") or {}
        value = extras.get("lgbtq") or profile.get("lgbtq")
        options = DEMOGRAPHIC_OPTIONS["lgbtq"]
        mapped = (
            _decline_if_requested(value, options) or _exact_option(value, options)
            if value
            else None
        )
        return "lgbtq", mapped, options
    if ftype == "input_checkbox" and "consent" in normed and "demographic" in normed:
        return "demographic_consent", None, []
    return None, None, []


class BrowserSession:
    """A persistent, single-page Chromium session for one user's application.
    Open once, fill once, then keep handling user edits until close()."""

    def __init__(
        self,
        application_url: str,
        *,
        headless: bool = False,
        resume_path: Optional[str] = None,
        resume_filename: Optional[str] = None,
        nav_timeout_ms: int = 30000,
    ):
        self.application_url = application_url
        self.headless = headless
        self.resume_path = resume_path
        self.resume_filename = resume_filename  # override filename shown to Greenhouse
        self.nav_timeout_ms = nav_timeout_ms

        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self.is_open = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Boot Chromium and navigate to the application page. Idempotent."""
        if self.is_open:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport=DEFAULT_VIEWPORT,
            locale="en-US",
        )
        self._page = await self._context.new_page()
        await self._page.goto(
            self.application_url,
            wait_until="domcontentloaded",
            timeout=self.nav_timeout_ms,
        )
        await self._wait_for_form()
        await asyncio.sleep(0.6)
        self.is_open = True

    async def close(self) -> None:
        """Tear down the browser. Safe to call multiple times."""
        if not self.is_open and self._pw is None:
            return
        for resource in (self._page, self._context, self._browser):
            if resource is not None:
                try:
                    await resource.close()
                except Exception:  # noqa: BLE001
                    pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self.is_open = False

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    async def initial_fill(
        self,
        filled_fields: list[dict[str, Any]],
        *,
        screenshot_every_n_fields: int = 3,
        type_delay_ms: int = 25,
    ) -> AsyncIterator[FillEvent]:
        """Walk through `filled_fields` and yield FillEvents as each one is
        typed/selected into the open page. Browser stays open after this
        generator completes."""
        if not self.is_open or self._page is None:
            yield FillEvent(kind="error", error="browser session is not open")
            return

        yield FillEvent(kind="started", message=f"Opening {self.application_url}")

        # First screenshot: blank form loaded.
        try:
            shot = await self._page.screenshot(full_page=False, type="png")
            yield FillEvent(
                kind="screenshot", message="Blank form loaded", screenshot_png=shot
            )
        except Exception:  # noqa: BLE001
            pass

        filled_since_shot = 0
        async with self._lock:
            for f in filled_fields:
                name = f.get("name")
                value = f.get("value")
                ftype = f.get("ftype") or ""
                if not name or value in (None, ""):
                    continue

                ok, detail = await self._fill_one(
                    name,
                    value,
                    ftype=ftype,
                    options=f.get("options") or [],
                    type_delay_ms=type_delay_ms,
                )
                yield FillEvent(
                    kind="field_filled" if ok else "field_skipped",
                    field_name=name,
                    value=value,
                    message=detail,
                )
                if ok:
                    filled_since_shot += 1

                if filled_since_shot >= screenshot_every_n_fields:
                    filled_since_shot = 0
                    try:
                        shot = await self._page.screenshot(full_page=False, type="png")
                        yield FillEvent(
                            kind="screenshot",
                            message=f"progress after `{name}`",
                            screenshot_png=shot,
                        )
                    except Exception:  # noqa: BLE001
                        pass

        # Final shot — same page, but full-page so user sees everything.
        try:
            final = await self._page.screenshot(full_page=True, type="png")
            yield FillEvent(
                kind="done",
                message="Form complete — browser stays open for edits",
                screenshot_png=final,
            )
        except Exception:  # noqa: BLE001
            yield FillEvent(kind="done", message="Form filled")

    async def apply_edit(
        self,
        name: str,
        value: Any,
        *,
        ftype: str = "",
        options: Optional[list] = None,
    ) -> tuple[bool, Optional[bytes], str]:
        """Type/select `value` into the open browser. Returns
        (success, screenshot_png_or_None, detail)."""
        if not self.is_open or self._page is None:
            return False, None, "browser session is not open"

        async with self._lock:
            ok, detail = await self._fill_one(
                name, value, ftype=ftype, options=options or [], type_delay_ms=25
            )
            png: Optional[bytes] = None
            if ok:
                try:
                    png = await self._page.screenshot(full_page=False, type="png")
                except Exception:  # noqa: BLE001
                    png = None
            return ok, png, detail

    async def take_screenshot(self, *, full_page: bool = True) -> Optional[bytes]:
        if not self.is_open or self._page is None:
            return None
        try:
            return await self._page.screenshot(full_page=full_page, type="png")
        except Exception:  # noqa: BLE001
            return None

    async def discover_profile_fillables(
        self, profile: dict[str, Any], *, known_names: set[str]
    ) -> list[dict[str, Any]]:
        """Find live-only Greenhouse fields absent from the boards API.

        Greenhouse renders some demographic fields only in the browser. They
        are required on the page, but missing from `/questions=true`; this
        method turns safe profile matches into normal fillable session fields
        and exposes ambiguous required fields so chat can ask the user.
        """
        if self._page is None or not profile:
            return []

        controls = await self._page.evaluate(
            """() => {
              function labelFor(el) {
                const id = el.id;
                if (id) {
                  const lab = document.querySelector(`label[for="${CSS.escape(id)}"]`);
                  if (lab) return lab.innerText.trim();
                }
                const wrap = el.closest('label');
                if (wrap) return wrap.innerText.trim();
                const group = el.closest('[class*="field"], [class*="question"], fieldset, .form-field, .application-question');
                if (group) return group.innerText.trim().slice(0, 600);
                return '';
              }
              function visible(el) {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return !!(r.width || r.height) && s.visibility !== 'hidden' && s.display !== 'none';
              }
              return Array.from(document.querySelectorAll('input, select, textarea, [role="combobox"]')).map(el => {
                const tag = el.tagName.toLowerCase();
                const type = (el.getAttribute('type') || '').toLowerCase();
                const role = el.getAttribute('role') || '';
                const label = labelFor(el);
                const id = el.id || '';
                const name = el.getAttribute('name') || '';
                const options = tag === 'select'
                  ? Array.from(el.options).map(o => ({label:o.textContent.trim(), value:o.value || o.textContent.trim()}))
                  : [];
                return {
                  tag, type, role, id, name, label, options,
                  required: !!el.required || el.getAttribute('aria-required') === 'true' || /\\*/.test(label),
                  visible: visible(el),
                };
              });
            }"""
        )

        discovered: list[dict[str, Any]] = []
        for control in controls:
            if not control.get("visible"):
                continue
            name = control.get("id") or control.get("name")
            if not name or name in known_names:
                continue

            label = _clean_label(control.get("label") or "")
            if not label:
                continue
            tag = control.get("tag") or "input"
            raw_type = control.get("type") or ""
            role = control.get("role") or ""
            ftype = (
                "input_checkbox"
                if raw_type == "checkbox"
                else (
                    "multi_value_single_select"
                    if tag == "select" or role == "combobox"
                    else "input_text"
                )
            )
            attr, value, options = _profile_value_for_live_label(
                profile, label, ftype=ftype
            )
            if not attr:
                continue

            # Snap the mapped value to the actual live options on the page.
            # This bridges gaps between our hardcoded labels and what Greenhouse
            # actually renders (e.g. "No, I don't have a disability" vs the
            # longer "No, I do not have a disability and have not had one in
            # the past").  We try three things in order:
            #   1. match_option on the already-mapped value
            #   2. match_option on the raw profile value (e.g. "No" / "Male" /
            #      "I am not a protected veteran") — usually shorter and more
            #      likely to hit an exact or yes/no-prefix match
            actual_opts = control.get("options") or []
            if actual_opts:
                snapped = match_option(value, actual_opts) if value else None
                if not snapped:
                    raw = profile.get(attr)
                    if raw is not None:
                        snapped = match_option(str(raw), actual_opts)
                if snapped:
                    value = snapped.get("value") or snapped.get("label") or value

            options = actual_opts or options
            required = bool(control.get("required"))
            discovered.append(
                {
                    "name": name,
                    "label": label,
                    "required": required,
                    "ftype": ftype,
                    "options": options or control.get("options") or [],
                    "value": value,
                    "source": "profile" if value else "live_required",
                    "confidence": 0.9 if value else 0.0,
                    "profile_attr": attr,
                }
            )
            known_names.add(name)
        return discovered

    async def fill_eeo_fields(
        self, profile: dict[str, Any]
    ) -> list[tuple[str, bool, str]]:
        """Directly fill EEO demographic dropdowns by matching their visible
        label text on the page.

        These fields are not returned by the Greenhouse boards API and are
        sometimes missed by discover_profile_fillables when their select
        elements have opaque / duplicate name attributes.  This method walks
        every visible <select> and [role=combobox] element on the page, calls
        _profile_value_for_live_label on its label, and selects the right
        option if a profile value is available.

        Returns a list of (label, success, detail) tuples.
        """
        if self._page is None or not profile:
            return []

        # EEO label keywords — only process elements whose label matches one
        # of these to avoid touching unrelated dropdowns.
        EEO_KEYWORDS = {
            "gender",
            "hispanic",
            "latino",
            "veteran",
            "disab",
            "ethnicity",
            "race",
            "sexual orientation",
            "transgender",
        }

        results: list[tuple[str, bool, str]] = []
        try:
            controls = await self._page.evaluate(
                """() => {
                  function labelFor(el) {
                    const id = el.id;
                    if (id) {
                      const lab = document.querySelector('label[for="' + CSS.escape(id) + '"]');
                      if (lab) return lab.innerText.trim();
                    }
                    const wrap = el.closest('label');
                    if (wrap) return wrap.innerText.trim();
                    const group = el.closest('[class*="field"],[class*="question"],fieldset,.form-field');
                    if (group) return group.innerText.trim().slice(0, 300);
                    return '';
                  }
                  function visible(el) {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return !!(r.width || r.height) && s.visibility !== 'hidden' && s.display !== 'none';
                  }
                  return Array.from(document.querySelectorAll('select, [role="combobox"]')).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    id: el.id || '',
                    name: el.getAttribute('name') || '',
                    label: labelFor(el),
                    visible: visible(el),
                    options: el.tagName.toLowerCase() === 'select'
                      ? Array.from(el.options).map(o => ({label: o.textContent.trim(), value: o.value || o.textContent.trim()}))
                      : [],
                  }));
                }"""
            )
        except Exception:  # noqa: BLE001
            return []

        for ctrl in controls:
            if not ctrl.get("visible"):
                continue
            raw_label = _clean_label(ctrl.get("label") or "")
            label_lc = raw_label.lower()
            if not any(kw in label_lc for kw in EEO_KEYWORDS):
                continue

            ftype = (
                "multi_value_single_select"
                if ctrl.get("tag") == "select" or ctrl.get("role") == "combobox"
                else "input_text"
            )
            attr, value, _ = _profile_value_for_live_label(
                profile, raw_label, ftype=ftype
            )
            if not attr or value is None:
                continue

            # Locate the element on the page using id > name > label-text.
            el_id = ctrl.get("id") or ""
            el_name = ctrl.get("name") or ""
            loc = None
            for sel in [
                f'[id="{_css_escape(el_id)}"]' if el_id else None,
                f'[name="{_css_escape(el_name)}"]' if el_name else None,
            ]:
                if not sel:
                    continue
                try:
                    candidate = self._page.locator(sel).first
                    if await candidate.count() > 0 and await candidate.is_visible(
                        timeout=300
                    ):
                        loc = candidate
                        break
                except Exception:  # noqa: BLE001
                    continue

            if loc is None:
                results.append((raw_label, False, "element not found on page"))
                continue

            tag = ctrl.get("tag", "input")
            target_label = str(value)
            target_value = str(value)

            # For native <select> with known options, snap the value first.
            actual_opts = ctrl.get("options") or []
            if actual_opts:
                snapped = match_option(str(value), actual_opts)
                if not snapped:
                    raw_prof = profile.get(attr)
                    if raw_prof is not None:
                        snapped = match_option(str(raw_prof), actual_opts)
                if snapped:
                    target_label = snapped.get("label") or target_label
                    target_value = snapped.get("value") or target_value

            try:
                if tag == "select":
                    for attempt_fn in (
                        lambda: loc.select_option(value=target_value),
                        lambda: loc.select_option(label=target_label),
                        lambda: loc.select_option(value=str(value)),
                        lambda: loc.select_option(label=str(value)),
                    ):
                        try:
                            await attempt_fn()
                            results.append(
                                (raw_label, True, f"selected `{target_label}`")
                            )
                            break
                        except Exception:  # noqa: BLE001
                            continue
                    else:
                        results.append((raw_label, False, "select_option exhausted"))
                else:
                    ok, detail = await self._select_styled_dropdown(
                        loc, el_id or el_name, target_label, target_value
                    )
                    results.append((raw_label, ok, detail))
            except Exception as exc:  # noqa: BLE001
                results.append((raw_label, False, str(exc)))

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _wait_for_form(self) -> bool:
        if self._page is None:
            return False
        candidates = [
            "#application_form",
            'form[action*="applications"]',
            'input[name="first_name"]',
            'input[name="job_application[first_name]"]',
        ]
        for sel in candidates:
            try:
                await self._page.wait_for_selector(
                    sel, state="visible", timeout=self.nav_timeout_ms // len(candidates)
                )
                return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _find_input_for_name(self, name: str) -> Optional[Locator]:
        if self._page is None:
            return None
        escaped = _css_escape(name)
        candidates = [
            f'[name="{escaped}"]',
            f'[name="job_application[{escaped}]"]',
            f'[id="{escaped}"]',
            f'[id$="_{escaped}"]',
            f'[name$="[{escaped}]"]',
        ]
        for sel in candidates:
            try:
                loc = self._page.locator(sel).first
                if await loc.count() > 0:
                    try:
                        if await loc.is_visible(timeout=200):
                            return loc
                    except Exception:  # noqa: BLE001
                        return loc
            except Exception:  # noqa: BLE001
                continue
        return None

    async def _fill_one(
        self,
        name: str,
        value: Any,
        *,
        ftype: str,
        options: Optional[list] = None,
        type_delay_ms: int = 25,
    ) -> tuple[bool, str]:
        if self._page is None:
            return False, "page is closed"
        ftype = (ftype or "").lower()
        options = options or []

        if ftype in {"input_file", "file", "attachment"}:
            if not self.resume_path:
                return False, "no resume file on disk"
            import shutil
            import tempfile

            attach_path = self.resume_path
            tmp_dir = None
            try:
                if self.resume_filename:
                    tmp_dir = tempfile.mkdtemp()
                    attach_path = str(Path(tmp_dir) / self.resume_filename)
                    shutil.copy2(self.resume_path, attach_path)

                # Greenhouse wraps file inputs in custom React/Dropzone widgets.
                # set_input_files() on the hidden <input> bypasses React handlers
                # and nothing gets registered.  The only reliable approach is to
                # intercept the native file-chooser dialog that React opens when
                # the visible upload button/link is clicked.
                #
                # Strategy (tried in order):
                #   1. Expect a file-chooser, then click any visible upload trigger
                #      near a file input on the page.
                #   2. If that fails, use set_input_files on the raw <input> and
                #      fire a synthetic 'change' event so React picks it up.

                # Broad selector covering Greenhouse "Attach" links, "Upload file"
                # buttons, Dropzone click zones, and generic file-chooser triggers.
                _UPLOAD_BTN_SEL = (
                    'a:has-text("Attach"), button:has-text("Attach"), '
                    'a:has-text("Upload"), button:has-text("Upload"), '
                    'a:has-text("Browse"), button:has-text("Browse"), '
                    'a:has-text("Choose"), button:has-text("Choose"), '
                    '[class*="dz-clickable"] button, [class*="dz-clickable"] a, '
                    '[class*="dropzone"] button, [class*="dropzone"] a, '
                    'label[class*="upload"], label[for*="resume"], '
                    'label[for*="file"]'
                )
                trigger = self._page.locator(_UPLOAD_BTN_SEL).first

                used_chooser = False
                try:
                    if await trigger.count() > 0:
                        async with self._page.expect_file_chooser(
                            timeout=8000
                        ) as fc_info:
                            try:
                                await trigger.click(timeout=3000)
                            except Exception:  # noqa: BLE001
                                # Container might intercept the click; try JS click
                                await trigger.evaluate("el => el.click()")
                        fc = await fc_info.value
                        await fc.set_files(attach_path)
                        used_chooser = True
                except Exception:  # noqa: BLE001
                    pass

                if not used_chooser:
                    # Last resort: set files directly on the hidden <input> and
                    # fire a synthetic change event so React/Dropzone registers it.
                    file_input = self._page.locator(
                        f'input[type="file"][name="{_css_escape(name)}"], '
                        f'input[type="file"][name="job_application[{_css_escape(name)}]"], '
                        f'input[type="file"][name*="{_css_escape(name)}"]'
                    ).first
                    if await file_input.count() == 0:
                        file_input = self._page.locator('input[type="file"]').first
                    await file_input.set_input_files(attach_path)
                    # Fire change + input events so React/Dropzone re-renders.
                    await file_input.evaluate(
                        "el => { el.dispatchEvent(new Event('change', {bubbles:true})); "
                        "el.dispatchEvent(new Event('input', {bubbles:true})); }"
                    )

                display_name = self.resume_filename or Path(attach_path).name
                return True, f"attached {display_name}"
            except Exception as exc:  # noqa: BLE001
                return False, f"file upload failed: {exc}"
            finally:
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        loc = await self._find_input_for_name(name)
        if loc is None:
            return False, "input not found on page"

        try:
            tag = await loc.evaluate("el => el.tagName.toLowerCase()")
        except Exception:  # noqa: BLE001
            tag = "input"
        try:
            input_type = await loc.evaluate(
                "el => (el.getAttribute('type') || '').toLowerCase()"
            )
        except Exception:  # noqa: BLE001
            input_type = ""

        try:
            await loc.scroll_into_view_if_needed(timeout=2000)
        except Exception:  # noqa: BLE001
            pass

        if ftype in {"input_checkbox", "checkbox"} or input_type == "checkbox":
            desired = _norm(value) not in {"", "0", "false", "no", "off", "none"}
            try:
                if desired:
                    await loc.check(timeout=1500)
                    return True, "checked checkbox"
                await loc.uncheck(timeout=1500)
                return True, "unchecked checkbox"
            except Exception as exc:  # noqa: BLE001
                return False, f"checkbox failed: {exc}"

        # Determine the actual option label/value we want to use.
        snap = match_option(value, options) if options else None
        target_label = snap["label"] if snap else str(value)
        target_value = snap["value"] if snap else str(value)

        try:
            # Native <select>.
            if tag == "select":
                for attempt in (
                    lambda: loc.select_option(value=target_value),
                    lambda: loc.select_option(label=target_label),
                    lambda: loc.select_option(value=str(value)),
                    lambda: loc.select_option(label=str(value)),
                ):
                    try:
                        await attempt()
                        return True, f"selected `{target_label}`"
                    except Exception:  # noqa: BLE001
                        continue
                return False, "select_option exhausted all attempts"

            # Greenhouse react-select / styled dropdowns. The original element
            # is an <input> (often type="text" with role=combobox). We click
            # it to open the listbox, then click the matching option.
            # IMPORTANT: try this even when `options` is empty — Greenhouse EEO
            # comboboxes are closed React dropdowns whose options aren't in the
            # DOM until clicked, so discover_profile_fillables returns options=[].
            # The ftype check ensures we still open-and-click for select fields.
            if options or ftype in {
                "multi_value_single_select",
                "multi_value_multi_select",
                "select",
                "combobox",
            }:
                ok, detail = await self._select_styled_dropdown(
                    loc, name, target_label, target_value
                )
                if ok:
                    return True, detail
                # If styled-dropdown click failed, fall through to typing as a
                # best-effort so the user sees *something* in the field.

            if ftype in {"input_radio", "radio"}:
                try:
                    radios = self._page.locator(
                        f'input[name="{_css_escape(name)}"][value="{_css_escape(target_value)}"]'
                    )
                    if await radios.count() > 0:
                        await radios.first.check(timeout=1500)
                        return True, f"checked radio `{target_value}`"
                except Exception:  # noqa: BLE001
                    pass

            try:
                await loc.fill("")
            except Exception:  # noqa: BLE001
                pass

            text_value = str(value) if not isinstance(value, list) else ", ".join(value)
            if len(text_value) <= 80:
                await loc.type(text_value, delay=type_delay_ms)
            else:
                await loc.fill(text_value)
            return True, f"typed {len(text_value)} chars"
        except Exception as exc:  # noqa: BLE001
            return False, f"interaction failed: {exc}"

    async def _select_styled_dropdown(
        self,
        trigger: Locator,
        name: str,
        target_label: str,
        target_value: str,
    ) -> tuple[bool, str]:
        """Open a Greenhouse-style react-select dropdown and click the
        option matching `target_label`. Returns (success, detail)."""
        if self._page is None:
            return False, "page closed"
        try:
            await trigger.click(timeout=2000)
        except Exception:  # noqa: BLE001
            # Sometimes the input itself isn't clickable but its parent
            # container is — click the container.
            try:
                await trigger.evaluate(
                    'el => (el.closest(\'[class*="select"],[class*="Select"]\') || el).click()'
                )
            except Exception:  # noqa: BLE001
                return False, "couldn't open dropdown"

        await asyncio.sleep(0.25)

        # The listbox is usually rendered into a portal. Scan [role="option"]
        # elements in three passes — from most to least specific — so that
        # short targets like "No" or "Male" don't accidentally match a longer
        # option that merely *contains* those letters (e.g. "Hispanic or
        # Latin**o**" or "Cisgender **man**").
        #   Pass 1 — exact match (case-insensitive)
        #   Pass 2 — prefix: option text starts with target, or target starts
        #            with option text (handles "No" → "No, I do not have …")
        #   Pass 3 — general substring in either direction (broad fallback)
        normalized_target = target_label.lower().strip()
        try:
            options_loc = self._page.locator('[role="option"]')
            count = await options_loc.count()
            opt_texts: list[tuple[int, str, str]] = []
            for i in range(count):
                opt = options_loc.nth(i)
                try:
                    txt = (await opt.inner_text(timeout=500)).strip()
                except Exception:  # noqa: BLE001
                    continue
                if txt:
                    opt_texts.append((i, txt, txt.lower().strip()))

            for pass_num in range(3):
                for i, txt, nt in opt_texts:
                    if pass_num == 0:
                        match = nt == normalized_target
                    elif pass_num == 1:
                        match = nt.startswith(
                            normalized_target
                        ) or normalized_target.startswith(nt)
                    else:
                        match = normalized_target in nt or nt in normalized_target
                    if match:
                        try:
                            await options_loc.nth(i).click(timeout=1500)
                            return True, f"clicked option `{txt}`"
                        except Exception:  # noqa: BLE001
                            continue
        except Exception:  # noqa: BLE001
            pass

        # Fallback: type the label into the now-focused combobox input and
        # press Enter — react-select treats this as a filter+select.
        try:
            await self._page.keyboard.type(target_label, delay=20)
            await asyncio.sleep(0.2)
            await self._page.keyboard.press("Enter")
            return True, f"filtered+entered `{target_label}`"
        except Exception as exc:  # noqa: BLE001
            return False, f"styled-dropdown failed: {exc}"
