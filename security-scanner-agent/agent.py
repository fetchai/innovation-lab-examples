import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from uagents import Agent, Bureau, Context

from models import ScanRequest, ScanResponse, Vulnerability


# Load .env from the parent folder (fetchai-learning/.env)
env_path = Path(__file__).parent.parent / ".env"
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


def scan_code(request: ScanRequest) -> ScanResponse:
    """Send code to ASI:One for security review, return structured result."""
    user_message = (
        f"Language: {request.language}\n\n"
        f"Code:\n```{request.language}\n{request.code}\n```"
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

        raw_output = response.choices[0].message.content
        parsed = json.loads(raw_output)

        vulnerabilities = [
            Vulnerability(**v) for v in parsed.get("vulnerabilities", [])
        ]

        return ScanResponse(
            scan_status="success",
            summary=parsed.get("summary", ""),
            vulnerabilities=vulnerabilities,
        )

    except Exception as e:
        return ScanResponse(
            scan_status="error",
            error_message=str(e),
        )


# ---- Test snippet (intentionally vulnerable) ----
# Replace this with any code you want to scan.
VULNERABLE_CODE = """
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return conn.execute(query).fetchone()

API_KEY = "sk_live_abc123xyz789supersecret"

def login(username, password):
    print(f"User {username} logged in with password {password}")
    return True
"""


# ---- Agents ----
scanner = Agent(name="scanner")
client_agent = Agent(name="client")


@scanner.on_message(model=ScanRequest)
async def handle_scan_request(ctx: Context, sender: str, msg: ScanRequest):
    """Scanner receives a request, runs the LLM scan, sends back a response."""
    ctx.logger.info(
        f"Scan request received ({len(msg.code)} chars, lang={msg.language})"
    )
    ctx.logger.info("Analyzing...")
    result = scan_code(msg)
    await ctx.send(sender, result)


@client_agent.on_interval(period=5.0)
async def send_initial_scan(ctx: Context):
    """Client sends one scan request, ~5 seconds after startup."""
    if ctx.storage.get("scan_sent"):
        return  # already sent, do nothing on subsequent ticks
    ctx.logger.info("Client online. Sending sample code to scanner...")
    request = ScanRequest(code=VULNERABLE_CODE, language="python")
    await ctx.send(scanner.address, request)
    ctx.storage.set("scan_sent", True)


@client_agent.on_message(model=ScanResponse)
async def handle_scan_result(ctx: Context, sender: str, msg: ScanResponse):
    """Client receives the scan response, logs it nicely."""
    if msg.scan_status == "error":
        ctx.logger.error(f"Scan failed: {msg.error_message}")
        return

    ctx.logger.info("")
    ctx.logger.info("=" * 60)
    ctx.logger.info(f"Scan complete: {msg.summary}")
    ctx.logger.info(f"Vulnerabilities found: {len(msg.vulnerabilities)}")
    ctx.logger.info("=" * 60)

    for i, vuln in enumerate(msg.vulnerabilities, 1):
        ctx.logger.info("")
        ctx.logger.info(
            f"#{i}  {vuln.type}  [{vuln.severity.upper()}]  line {vuln.line_number}"
        )
        ctx.logger.info(f"    {vuln.description}")
        ctx.logger.info(f"    Fix: {vuln.suggested_fix}")


bureau = Bureau()
bureau.add(scanner)
bureau.add(client_agent)


if __name__ == "__main__":
    bureau.run()
