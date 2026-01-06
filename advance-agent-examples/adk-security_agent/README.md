# Security & Guardrails Agent 🛡️

**Prompt Engineering is NOT a Security Strategy** 🚫

An enterprise-grade security assistant that demonstrates **defense-in-depth** security strategy. Built with [Google ADK](https://google.github.io/adk-docs/) and [Fetch.ai uAgents](https://uagents.fetch.ai/docs), this agent provides security best practices, compliance guidance, and risk identification while enforcing multiple layers of security protection.

## Features

- **Defense-in-depth architecture**: Multiple security layers (Model Armor, Callbacks, Plugins, Identity Management)
- **Role-based access control**: Five user roles (student, developer, enterprise, business, robot) with appropriate permissions
- **Model Armor integration**: Infrastructure-level protection against PII, hate speech, and jailbreaks
- **Security callbacks**: Deterministic Python logic for role verification and access control
- **Monitoring plugins**: Audit logging and security event tracking
- **Identity verification**: User identity storage and verification through uAgents storage
- **Multi-turn chat with memory**: Conversations persist with user identity across sessions
- **uAgents chat compatibility**: Works out-of-the-box with uAgents / ASI:One chat UIs

## Defense-in-Depth Architecture

ADK replaces "trust" with "verification" through a **tiered architecture**:

### 🛡️ The Infrastructure Layer: Model Armor

Model Armor sits at the gateway level, inspecting every input and output 🔍. It provides a global kill-switch 🔌 for toxic content and injection attacks, ensuring safety even if the agent code is compromised.

**What Model Armor Protects:**
- ✅ **Hate Speech** filtering (MEDIUM_AND_ABOVE confidence)
- ✅ **Harassment** filtering (HIGH confidence)
- ✅ **PII detection and blocking** (LOW_AND_ABOVE confidence)
- ✅ **Jailbreak attack prevention**
- ✅ **Multi-language detection**

**Configuration:** See `security_agent/model_armor_config.sh` for setup instructions.

### 🔵 The Developer Layer: Callbacks & Plugins

**Stop leaking data before it leaves your container** 🛑. Use ADK Callbacks to inject deterministic Python logic before_agent execution. This acts as middleware—validating user profiles, checking roles, and blocking unauthorized access before the model ever sees the prompt.

**Key Features:**
- Runs **before** the LLM sees the data
- Deterministic Python logic (not probabilistic)
- Validates user profiles, sessions, roles
- Blocks unauthorized access
- Custom business logic enforcement

### 📊 The Monitoring Layer: Plugins

Plugins provide observability and auditing:
- Track agent invocations
- Monitor usage patterns
- Security audit logging
- Performance metrics

## Security Layers Summary

```
Level 1: Model Armor (Infrastructure)
  └─ Global protection, cannot be bypassed
     └─ Blocks: Toxic content, PII, Jailbreaks

Level 2: Identity Verification (Storage)
  └─ User roles stored and verified
     └─ Validates: student/developer/enterprise/business/robot

Level 3: Callbacks (Developer Code)
  └─ Custom business logic
     └─ Validates: User profiles, Sessions, Roles, Permissions

Level 4: Plugins (Monitoring)
  └─ Observability and auditing
     └─ Tracks: Invocations, Usage patterns, Security events
```

## Prerequisites

- Python 3.10+
- Google Cloud Project with:
  - Gemini API enabled
  - Model Armor template configured (optional but recommended)
  - API key for authentication

## Installation

### Local Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

Copy the example environment file and update with your values:

```bash
cp .env.example .env
# Then edit .env with your API key and configuration
```

Or set the environment variables directly:

```bash
export GOOGLE_API_KEY=your-gemini-api-key
# OR
export GEMINI_API_KEY=your-gemini-api-key

# Optional: Model Armor Configuration
export GOOGLE_CLOUD_PROJECT=your-project-id
export MODEL_ARMOR_TEMPLATE=security_guardrails_template
export MODEL_ARMOR_LOCATION=us-central1
```

Get your API key from: https://aistudio.google.com/app/apikey

## Usage

### Run Locally

```bash
python -m security_agent.agent
```

The agent will start on `http://0.0.0.0:8008`

### Run with Docker

```bash
# Build and run
docker-compose up --build

# Or run in background
docker-compose up -d
```

### Example Queries

#### First-Time User Flow

**Request 1:**
```
User: hi
Agent: 👋 Welcome! Please identify yourself by replying with **one** of the following:

• **student**
• **developer**
• **enterprise**
• **business**
• **robot**

This will help me provide you with the appropriate access and assistance.
```

**Request 2:**
```
User: developer
Agent: ✅ Thank you! Your identity has been saved as: **Developer**. How can I help you today?
```

#### Security Best Practices Queries

```
"What are the best practices for secure password storage?"
"How do I implement GDPR compliance in my application?"
"What is OWASP Top 10?"
"How do I implement rate limiting in my API?"
"What encryption methods should I use for data at rest?"
"What are the best authentication methods for web applications?"
"Explain SOC2 compliance requirements"
"How should I handle security vulnerabilities in production?"
```

#### Role-Based Access Examples

**Student Query:**
```
"What is encryption?"
→ Provides educational response with basic concepts
```

**Developer Query:**
```
"How do I configure IAM roles for service accounts?"
→ Provides detailed technical guidance with code examples
```

**Enterprise Query:**
```
"What security policies should we implement for our organization?"
→ Provides enterprise-level security policy recommendations
```

#### Model Armor Protection Examples

**PII Detection (Blocked by Model Armor):**
```
User: My email is john@example.com and my phone is 555-1234
→ Model Armor automatically detects and blocks PII
```

**Hate Speech (Blocked by Model Armor):**
```
User: [Hate speech content]
→ Model Armor filters based on MEDIUM_AND_ABOVE confidence
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              uAgents Chat Protocol                      │
│              (Message Handler with Identity Storage)     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Identity Verification                       │
│              (Role-based Access Control)                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ADK Runner                                  │
│              (Agent Execution with Callbacks & Plugins)  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Security Agent                              │
│              - before_agent_callback (Role Verification) │
│              - Monitoring Plugin (Audit Logging)         │
│              Model: gemini-2.5-flash                     │
│              Tools: google_search                        │
│              Model Armor: Infrastructure-level protection│
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
security_agent/
├── agent.py                    # Main agent file with uAgents integration
├── app_setup.py                # ADK agent setup with callbacks and plugins
├── callback_and_plugins.py     # Security callbacks and monitoring plugins
├── adk_plugin.py               # Custom ADK plugin for invocation tracking
└── model_armor_config.sh       # Model Armor configuration script
```

## Production Considerations

⚠️ **Important**: This agent demonstrates security patterns:

- **Model Armor**: Configure at infrastructure level (required for production)
- **Callbacks**: Customize for your use case and business logic
- **Plugins**: Extend for production monitoring needs
- **Identity Management**: Integrate with your authentication system
- **State Management**: Use persistent storage in production

**Production Checklist:**
- ✅ Configure Model Armor templates for your organization
- ✅ Replace in-memory storage with persistent database
- ✅ Integrate with OAuth, JWT, or session management
- ✅ Add distributed rate limiting
- ✅ Enhance monitoring with SIEM systems
- ✅ Configure proper IAM roles and permissions

## References

- [Model Armor Documentation](https://docs.cloud.google.com/model-armor/overview)
- [Agent Identity](https://docs.cloud.google.com/agent-builder/agent-engine/agent-identity)
- [ADK Callbacks](https://google.github.io/adk-docs/callbacks/)
- [ADK Plugins](https://google.github.io/adk-docs/plugins/)
- [A2A Protocol](https://a2a-protocol.org/latest/topics/enterprise-ready/#tracing-observability-and-monitoring)

## Summary

✅ **Don't rely on:** "Please ignore PII" in prompts (wishful thinking)

✅ **Do use:** Model Armor (infrastructure) + Callbacks (code) + Plugins (monitoring) = Real security

This agent demonstrates how to combine:
- **Infrastructure Layer** (Model Armor) for global protection
- **Developer Layer** (Callbacks & Plugins) for custom logic
- **Identity Management** (uAgents Storage) for access control
- **uAgents Integration** for chat protocol communication

**Result:** Defense-in-depth security that treats the LLM as an untrusted component.
