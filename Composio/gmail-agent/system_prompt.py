"""
Centralized system prompts and constants used across the app.
"""

# High-level flow description for documentation and debugging
SYSTEM_FLOW = (
    "System Flow (Agent):\n\n"
    "1) Parse chat input for email intent: send or fetch. Extract fields (to, subject, body) and optional From:.\n"
    "2) On connect, remember the authenticated email per chat sender; use it for all actions. No hardcoded defaults.\n"
    "3) Send: use LangChain + Composio with GMAIL_SEND_EMAIL.\n"
    "4) Fetch: call GMAIL_FETCH_EMAILS directly to avoid context bloat (supports labels, counts).\n"
    "5) Reply: call GMAIL_REPLY_TO_THREAD.\n"
    "6) Trash: call GMAIL_MOVE_TO_TRASH.\n"
    "7) Contacts: call GMAIL_GET_CONTACTS.\n"
    "8) Respond in Markdown with clear details (IDs, labels, previews)."
)

# Hub prompt used to build the functions agent
HUB_PROMPT_NAME = "hwchase17/openai-functions-agent"

# Default help text that the agent can send
DEFAULT_HELP_TEXT = """📧 Gmail Agent Help

Connect your account:
- Connect to my mail your@email.com

Send an email:
- Send email to: recipient@example.com, Subject: Hello, Body: How are you?
- Optionally add From: you@example.com (otherwise I use your connected email).

Fetch emails:
- Please fetch the 10 emails from my inbox
- Fetch emails (defaults to last 10 from INBOX)

Reply to a thread:
- Reply to: user@example.com, Thread Id: 1995..., Body: Thanks!

Move email to trash:
- Move to trash, Message Id: 1875f42779f726f2

Get contacts:
- Get contacts (lists names and emails)

Search people:
- Search people, Query: John Doe

Drafts:
- Create draft: To: user@example.com, Subject: Hello, Body: Hi there
- Send draft: Draft Id: r123abc
- Delete draft: Draft Id: r123abc

Thread messages:
- Fetch thread, Thread Id: 1995...

Profile:
- Get profile

Notes:
- I remember your authenticated email per chat; no hardcoded defaults.
- You can also include From: you@example.com in any message to switch the active account."""


