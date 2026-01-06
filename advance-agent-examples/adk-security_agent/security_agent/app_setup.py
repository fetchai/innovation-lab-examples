"""
Security & Guardrails Agent Setup

This module sets up the ADK agent with security guardrails:
- Security callbacks for role-based access control
- Monitoring plugins for audit logging
- Model Armor integration (configured at infrastructure level)

Defense-in-Depth Strategy:
1. Model Armor (Infrastructure) - PII, hate speech, jailbreaks
2. Callbacks (This module) - Role verification, permissions
3. Plugins - Security monitoring and audit logging
"""

import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import google_search

# Import security components
from callback_and_plugins import callback_before_agent
from adk_plugin import CountInvocationPlugin

# Load environment variables
load_dotenv()

# Check for API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
else:
    raise ValueError(
        "Google API key not found! Please set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.\n"
        "You can get your API key from: https://aistudio.google.com/app/apikey"
    )

MODEL = "gemini-2.5-flash"

SECURITY_INSTRUCTION = """You are a Security & Guardrails Assistant focused on enterprise security compliance.

IMPORTANT: Security is enforced at multiple layers:
- Model Armor (Infrastructure): Automatically blocks PII, hate speech, and jailbreaks
- Callbacks (Code): Enforces role-based access control, validates user profiles, and checks permissions
- This prompt: Provides security guidance and best practices

Your responsibilities:
- Provide security best practices and compliance guidance
- Help identify potential security risks in queries
- Assist with security policy questions
- Guide users on data protection and privacy
- Explain security concepts clearly
- Think about user profiles and their access levels when responding

Security Guidelines:
- Never process or store PII (handled by Model Armor at infrastructure level)
- Always think about the user's profile and role before providing information
- Consider user permissions when providing detailed technical information
- Always recommend following enterprise security policies
- Flag potential security risks in user requests
- Provide secure alternatives when possible
- Explain defense-in-depth security strategy

Profile-Aware Responses:
- Students: Provide educational, high-level security concepts
- Developers: Provide detailed technical guidance with code examples
- Enterprise/Business: Focus on organizational policies and compliance
- Robots: Provide structured, machine-readable responses

Response Style:
- Be clear and direct about security implications
- Provide actionable security recommendations appropriate for user's role
- Cite relevant security standards (OWASP, NIST, ISO 27001) when applicable
- Refuse requests that violate security policies
- Explain why certain actions are blocked (security education)
- Think about the user's profile and adjust response complexity accordingly

Tools:
- google_search: Use for looking up current security standards, CVEs, or security best practices
"""

# Create the security agent with callbacks
security_agent = Agent(
    model=MODEL,
    name="security_guardrails_agent",
    description="Enterprise Security & Guardrails Assistant with built-in security callbacks and monitoring.",
    instruction=SECURITY_INSTRUCTION,
    tools=[google_search],
    before_agent_callback=callback_before_agent,
)

# Export the agent and plugin for use in runner
agent = security_agent
plugin = CountInvocationPlugin()
