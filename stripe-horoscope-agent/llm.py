import asyncio

from openai import OpenAI

from config import ASI_ONE_API_KEY

client = OpenAI(api_key=ASI_ONE_API_KEY, base_url="https://api.asi1.ai/v1")

def _normalize_horoscope_output(text: str) -> str:
    """
    Enforce:
    - No disclaimer text
    - Output ends with exactly two lines:
      Lucky color: <color>
      Lucky numbers: <n1>, <n2>, <n3>
    """
    if not text:
        return ""

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Strip any disclaimer-like lines.
    cleaned: list[str] = []
    for ln in lines:
        l = ln.lower()
        if "for entertainment purposes only" in l:
            continue
        cleaned.append(ln)

    joined = "\n".join(cleaned)

    lucky_color: str | None = None
    lucky_numbers: str | None = None

    for ln in cleaned:
        if "lucky color:" in ln.lower():
            lucky_color = ln.split(":", 1)[1].strip() if ":" in ln else None
        if "lucky numbers:" in ln.lower():
            lucky_numbers = ln.split(":", 1)[1].strip() if ":" in ln else None

    # Handle case where both appear on one line.
    if (lucky_color is None or lucky_numbers is None) and ("lucky color:" in joined.lower()):
        lower = joined.lower()
        try:
            lc_idx = lower.rindex("lucky color:")
            ln_idx = lower.rindex("lucky numbers:")
            if lc_idx < ln_idx:
                lucky_color = joined[lc_idx:].split(":", 1)[1].split("Lucky numbers:", 1)[0].strip()
                lucky_numbers = joined[ln_idx:].split(":", 1)[1].strip()
        except Exception:
            pass

    # Remove any existing lucky lines from the main body.
    body_lines = []
    for ln in cleaned:
        l = ln.lower()
        if "lucky color:" in l or "lucky numbers:" in l:
            continue
        body_lines.append(ln)

    body = "\n".join(body_lines).strip()

    lucky_color_line = f"Lucky color: {lucky_color}" if lucky_color else "Lucky color: Blue"

    if lucky_numbers:
        nums = [n.strip() for n in lucky_numbers.replace(";", ",").split(",") if n.strip()]
        lucky_numbers_line = "Lucky numbers: " + ", ".join(nums[:3]) if nums else "Lucky numbers: 7, 19, 42"
    else:
        lucky_numbers_line = "Lucky numbers: 7, 19, 42"

    if body:
        return f"{body}\n{lucky_color_line}\n{lucky_numbers_line}".strip()
    return f"{lucky_color_line}\n{lucky_numbers_line}".strip()


async def generate_horoscope(sign: str) -> str:
    r = await asyncio.to_thread(
        client.chat.completions.create,
        model="asi1",
        temperature=0.7,
        max_tokens=250,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly astrologer. Write a *horoscope of the day* for the user's star sign.\n"
                    "Rules:\n"
                    "- 5 to 8 sentences\n"
                    "- Positive, practical, and specific\n"
                    "- No mention of payment\n"
                    "- Do NOT include any disclaimer text\n"
                    "- End with EXACTLY these two lines:\n"
                    "  Lucky color: <one color>\n"
                    "  Lucky numbers: <3 integers 1-99, comma-separated>"
                ),
            },
            {"role": "user", "content": f"My star sign is {sign}. Give me my horoscope of the day."},
        ],
    )
    return _normalize_horoscope_output((r.choices[0].message.content or "").strip())


async def normal_reply(user_text: str) -> str:
    r = await asyncio.to_thread(
        client.chat.completions.create,
        model="asi1",
        temperature=0.2,
        max_tokens=160,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are `stripe-horoscope-agent`.\n"
                    "Your ONLY capability is to sell and deliver a 'horoscope of the day' via chat.\n"
                    "Rules:\n"
                    "- Never claim you can browse the web, search, call tools, see images, or do anything else.\n"
                    "- If the user asks what you can do, explain: they can say 'give me my horoscope', you’ll ask for their star sign, request a $1 Stripe payment, then you’ll reply with the horoscope.\n"
                    "- If the user asks for anything unrelated, politely say you can only provide a paid daily horoscope.\n"
                    "- Keep responses short (1-4 sentences)."
                ),
            },
            {"role": "user", "content": user_text},
        ],
    )
    return (r.choices[0].message.content or "").strip()

