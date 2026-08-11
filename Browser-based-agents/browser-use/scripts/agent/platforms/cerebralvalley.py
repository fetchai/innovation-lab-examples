"""
Cerebral Valley platform registration handler.

CV uses Clerk for auth and has a structured application form.
Flow:
  1. Navigate to /e/<slug>
  2. Click "Apply" button
  3. Sign in with email (Clerk magic link or password)
  4. Fill each question in order
  5. Accept waiver checkbox
  6. Submit
"""

from playwright.async_api import Page


async def register(
    page: Page,
    event_url: str,
    profile,
    answers: dict[str, str],
) -> dict:
    """
    Run the Cerebral Valley registration flow.
    Returns {"success": bool, "message": str, "screenshot": str|None}
    """
    try:
        print(f"  [CV] Navigating to {event_url}")
        await page.goto(event_url, wait_until="networkidle", timeout=30000)

        # Click Apply / Register button
        apply_btn = page.locator(
            "button:has-text('Apply'), button:has-text('Register'), "
            "a:has-text('Apply'), a:has-text('Register')"
        ).first
        await apply_btn.wait_for(state="visible", timeout=10000)
        await apply_btn.click()
        await page.wait_for_load_state("networkidle")

        # Handle Clerk login if needed
        if "sign-in" in page.url or "signin" in page.url or await _is_signin_page(page):
            print("  [CV] Login required")
            result = await _handle_login(page, profile)
            if not result:
                return {
                    "success": False,
                    "message": "Login failed — check credentials in profile",
                }

        # Fill form fields
        await _fill_form(page, answers, profile)

        # Accept waiver if present
        await _accept_waiver(page)

        # Submit
        submit_btn = page.locator(
            "button[type='submit'], button:has-text('Submit'), button:has-text('Apply')"
        ).last
        await submit_btn.wait_for(state="visible", timeout=5000)
        await submit_btn.click()
        await page.wait_for_load_state("networkidle")

        # Check success
        success = await _check_success(page)
        screenshot = await page.screenshot()

        return {
            "success": success,
            "message": "Application submitted!"
            if success
            else "Submitted but confirmation unclear",
            "screenshot": screenshot,
            "final_url": page.url,
        }

    except Exception as e:
        screenshot = await page.screenshot()
        return {"success": False, "message": str(e), "screenshot": screenshot}


async def _is_signin_page(page: Page) -> bool:
    return bool(
        await page.query_selector("input[type='email'][placeholder*='email' i]")
    )


async def _handle_login(page: Page, profile) -> bool:
    """Handle Clerk email login."""
    try:
        email_input = page.locator("input[type='email']").first
        await email_input.fill(profile.cerebralvalley_email or profile.email)

        # Try password login first
        pwd_input = page.locator("input[type='password']").first
        if await pwd_input.count() > 0 and profile.cerebralvalley_password:
            await pwd_input.fill(profile.cerebralvalley_password)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            return True

        # Otherwise submit email for magic link / OTP
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)

        # Check for OTP input
        otp_input = page.locator("input[autocomplete='one-time-code']").first
        if await otp_input.count() > 0:
            print("  [CV] OTP required — check your email and enter the code:")
            otp = input("  OTP code: ").strip()
            await otp_input.fill(otp)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle")
            return True

        return True
    except Exception as e:
        print(f"  [CV] Login error: {e}")
        return False


async def _fill_form(page: Page, answers: dict[str, str], profile) -> None:
    """Fill visible form inputs by matching labels to answers."""
    # Get all visible text inputs and textareas
    inputs = await page.query_selector_all(
        "input[type='text'], input[type='url'], textarea"
    )

    for inp in inputs:
        try:
            # Find label associated with this input
            label_text = await _get_label(page, inp)
            if not label_text:
                continue

            # Match against our answer dict
            answer = _match_answer(label_text, answers, profile)
            if answer:
                await inp.click()
                await inp.fill(answer)
                await page.wait_for_timeout(100)
        except Exception:
            pass


async def _get_label(page: Page, element) -> str:
    """Find the label text for an input element."""
    try:
        # Try aria-label
        aria = await element.get_attribute("aria-label")
        if aria:
            return aria

        # Try associated <label>
        elem_id = await element.get_attribute("id")
        if elem_id:
            label = await page.query_selector(f"label[for='{elem_id}']")
            if label:
                return (await label.inner_text()).strip()

        # Try placeholder
        placeholder = await element.get_attribute("placeholder")
        if placeholder:
            return placeholder

        # Try parent label
        parent_label = await element.evaluate(
            "el => el.closest('label')?.innerText || ''"
        )
        return parent_label.strip()
    except Exception:
        return ""


def _match_answer(label: str, answers: dict[str, str], profile) -> str:
    """Find the best matching answer for a form label."""
    label_lower = label.lower()

    # Direct match in answers dict
    for question, answer in answers.items():
        if any(word in label_lower for word in question.lower().split()[:3]):
            return answer

    # Fallback to profile fields
    if "linkedin" in label_lower:
        return profile.linkedin_url
    if "github" in label_lower:
        return profile.github_url
    if "twitter" in label_lower or "x.com" in label_lower:
        return profile.twitter_url()
    if "email" in label_lower:
        return profile.email
    if "name" in label_lower:
        return profile.full_name()

    return ""


async def _accept_waiver(page: Page) -> None:
    """Check any waiver/terms checkboxes."""
    try:
        checkboxes = await page.query_selector_all("input[type='checkbox']")
        for cb in checkboxes:
            is_checked = await cb.is_checked()
            if not is_checked:
                await cb.click()
                await page.wait_for_timeout(200)
    except Exception:
        pass


async def _check_success(page: Page) -> bool:
    """Detect if submission was successful."""
    content = await page.content()
    success_signals = [
        "application received",
        "thank you",
        "you're in",
        "successfully",
        "submitted",
        "applied",
        "confirmed",
    ]
    return any(s in content.lower() for s in success_signals)
