import os
import re
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI
from uagents import Agent, Bureau, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from models import ScanResponse, Vulnerability


# Load .env (from same folder when running locally inside security-scanner-agent/)
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

llm_client = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1",
)


SYSTEM_PROMPT = """You are an expert security code reviewer. Analyze code for security vulnerabilities.

Look for issues including (but not limited to):
- Injection: SQL, NoSQL, command, LDAP, XPath
- Authentication & session management flaws
- Sensitive data exposure: hardcoded secrets, credentials in logs
- Insecure deserialization (pickle.loads, yaml.load without SafeLoader)
- Broken access control, IDOR
- XSS, CSRF
- Use of unsafe functions (eval, exec, shell=True without sanitization)
- Insufficient input validation

Severity guide:
- critical: remote code execution, auth bypass, full data exfiltration
- high: significant exposure under realistic conditions
- medium: meaningful risk but limited impact
- low: best-practice issue or minor exposure

Return JSON only, in this exact structure:
{
  "scan_status": "success",
  "summary": "<one-sentence overall risk assessment>",
  "vulnerabilities": [
    {
      "type": "<vulnerability category>",
      "severity": "<low|medium|high|critical>",
      "line_number": <integer or null>,
      "description": "<clear explanation>",
      "suggested_fix": "<concrete remediation>"
    }
  ]
}

If no vulnerabilities, return an empty array for vulnerabilities.
Output JSON only. No prose before or after."""


# ---- Helpers ----

def extract_code(text: str) -> str:
    """Pull code out of a markdown fence if present, else return the text as-is."""
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def scan_code(code: str, language: str = "python") -> ScanResponse:
    """Send code to ASI:One for security review, return structured result."""
    user_message = (
        f"Language: {language}\n\n"
        f"Code:\n```{language}\n{code}\n```"
    )

    try:
        response = llm_client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        parsed = json.loads(response.choices[0].message.content)

        vulnerabilities = [
            Vulnerability(**v) for v in parsed.get("vulnerabilities", [])
        ]

        return ScanResponse(
            scan_status="success",
            summary=parsed.get("summary", ""),
            vulnerabilities=vulnerabilities,
        )

    except Exception as e:
        return ScanResponse(scan_status="error", error_message=str(e))


def format_scan_as_markdown(scan: ScanResponse) -> str:
    """Format a ScanResponse into a readable markdown string for chat reply."""
    if scan.scan_status == "error":
        return f"⚠️ **Scan failed:** {scan.error_message}"

    if not scan.vulnerabilities:
        return f"✅ **No vulnerabilities found.**\n\n**Summary:** {scan.summary}"

    lines = [
        f"**Summary:** {scan.summary}",
        "",
        f"**Vulnerabilities found:** {len(scan.vulnerabilities)}",
        "",
    ]
    for i, vuln in enumerate(scan.vulnerabilities, 1):
        lines.extend([
            f"### {i}. {vuln.type} `[{vuln.severity.upper()}]`",
            f"- **Line:** {vuln.line_number}",
            f"- **Description:** {vuln.description}",
            f"- **Fix:** {vuln.suggested_fix or 'No specific fix suggested'}",
            "",
        ])
    return "\n".join(lines)


def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    """Wrap plain text in a ChatMessage with optional end-session marker."""
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )


# ---- Scanner agent (chat protocol) ----

scanner = Agent(
    name="security_scanner",
    seed="mallika_scanner_2026_xyz",
    port=8001,
    mailbox=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Process incoming chat messages — extract code, scan, reply."""
    # Always acknowledge first
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.utcnow(),
        acknowledged_msg_id=msg.msg_id,
    ))

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Session started with {sender}")
            continue
        if isinstance(item, EndSessionContent):
            ctx.logger.info(f"Session ended with {sender}")
            continue
        if isinstance(item, TextContent):
            ctx.logger.info(f"Scan request received from {sender}")
            code = extract_code(item.text)
            ctx.logger.info(f"Analyzing {len(code)} chars of code...")
            scan = scan_code(code)
            reply = create_text_chat(format_scan_as_markdown(scan))
            await ctx.send(sender, reply)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Log acknowledgements (no further action)."""
    ctx.logger.info(f"Ack from {sender} for {msg.acknowledged_msg_id}")


scanner.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    scanner.run()