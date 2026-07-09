# 🌤️ Real-time Weather Monitoring Agent

A minimal, beginner-friendly uAgent that demonstrates the **chat protocol** and **external REST API integration** using the free [OpenWeatherMap API](https://openweathermap.org/api).

> ⏱️ **You can have this running in under 5 minutes** — no credit card, no paid API, no complex setup.

---

## What it does

Send any city name through the Agentverse chat interface (or ASI:One) and the agent will reply with:

| Field | Example |
|---|---|
| 🌡️ Temperature | 28.4 °C (feels like 31.0 °C) |
| 💧 Humidity | 72% |
| 💨 Wind speed | 14.4 km/h |
| ☁️ Condition | Partly cloudy |
| 🚨 Heat alert | Triggered when temp > threshold |

---

## Folder structure

```
contributors/weather-monitor-agent/
├── README.md            ← you are here
├── requirements.txt     ← Python dependencies
├── .env.example         ← copy to .env and fill in your keys
├── agent.py             ← the uAgent (< 200 lines, heavily commented)
└── assets/
    └── demo.png         ← screenshot of the agent in action
```

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10 or higher |
| pip | latest |

---

## Quick start

### 1. Clone the repo and navigate to this folder

```bash
git clone https://github.com/fetchai/innovation-lab-examples.git
cd innovation-lab-examples/contributors/weather-monitor-agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get your free API keys

#### OpenWeatherMap (required)

1. Go to <https://openweathermap.org/api> and click **Sign In → Create an Account** (free, no credit card).
2. After signing in, go to **API keys** in your profile.
3. Copy the default key (or generate a new one).

> ⚠️ New keys can take up to **1 hour** to activate. If you get a 401 error right after signing up, wait a bit and try again.

#### Agentverse (optional — for Agentverse / ASI:One access)

1. Go to <https://agentverse.ai> and sign in.
2. Navigate to **API Keys** and create a new key.

### 5. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
OPENWEATHER_API_KEY=abc123...       # required
AGENTVERSE_API_KEY=your_key_here    # optional – leave blank for local-only mode
AGENT_SEED=my-unique-seed-phrase    # any passphrase; keeps your agent address stable
AGENT_PORT=8010                     # port for local HTTP endpoint
TEMP_ALERT_THRESHOLD=35.0           # °C – alert fires when temp exceeds this
```

### 6. Run the agent

```bash
python agent.py
```

You'll see output like:

```
INFO  [WeatherMonitorAgent] Weather Monitor Agent started  |  address: agent1q...
INFO  [WeatherMonitorAgent] Temperature alert threshold    : 35.0°C
```

---

## Talking to the agent

### Option A — via Agentverse chat (recommended)

1. Set `AGENTVERSE_API_KEY` in `.env` and restart the agent.
2. Open <https://agentverse.ai>, go to **My Agents**, find **WeatherMonitorAgent**.
3. Click **Chat** and send a message:

```
weather in Tokyo
```

or just:

```
Mumbai
```

or with country code for disambiguation:

```
Paris,FR
```

### Option B — local agent-to-agent message

Write a small test sender script using uAgents and send a `ChatMessage` to `agent1q<your_address>` on port 8010.

---

## Example responses

**Normal response**

```
🌤️  Weather in Mumbai, IN
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌡️  Temperature : 31.2°C  (feels like 34.8°C)
💧  Humidity    : 85%
💨  Wind speed  : 18.0 km/h
☁️  Condition   : Overcast clouds
```

**Heat alert triggered**

```
🌤️  Weather in Dubai, AE
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌡️  Temperature : 42.0°C  (feels like 47.1°C)
💧  Humidity    : 40%
💨  Wind speed  : 9.0 km/h
☁️  Condition   : Clear sky

🚨 Heat Alert! Temperature is above 35.0°C — stay hydrated and avoid direct sunlight.
```

---

## How it works (architecture)

```
User (ASI:One / Agentverse chat)
        │
        │  ChatMessage  (city name as free text)
        ▼
┌─────────────────────────────┐
│   WeatherMonitorAgent       │
│                             │
│  1. ACK the message         │
│  2. Parse city from text    │
│  3. httpx → OWM REST API    │
│  4. Check temp threshold    │
│  5. Send ChatMessage reply  │
└─────────────────────────────┘
        │
        │  ChatMessage  (formatted weather + optional alert)
        ▼
User
```

### Key files explained

| File | What it does |
|---|---|
| `agent.py` | Defines the uAgent, chat protocol handlers, `_fetch_weather()`, `_format_response()`, and `_extract_city()` |
| `.env` | Holds your API keys and configuration — never commit this file |
| `requirements.txt` | Four packages: `uagents`, `uagents-core`, `httpx`, `python-dotenv` |

---

## Configuring the alert threshold

By default the agent fires a heat alert when the temperature exceeds **35 °C**.  
Change this by editing `TEMP_ALERT_THRESHOLD` in your `.env`:

```env
TEMP_ALERT_THRESHOLD=30.0   # alert above 30 °C
```

No code change needed — the agent reads this at startup.

---

## Demo

![Demo screenshot](assets/demo.png)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` from OWM | API key is wrong or not yet active (new keys take up to 1 h) |
| `404 City not found` | Check spelling; try `City,CountryCode` e.g. `Springfield,US` |
| Agent address changes every restart | Make sure `AGENT_SEED` is set in `.env` |
| No response in Agentverse chat | Confirm `AGENTVERSE_API_KEY` is set and the agent is running |
| `ModuleNotFoundError` | Activate your virtual environment: `source .venv/bin/activate` |

---

## Contributing

Found a bug or want to extend this agent?  
Ideas: multi-city comparison, hourly forecast, unit toggle (°C/°F), language support.

Open an issue or PR — PRs referencing the parent issue with `Closes #131` are welcome!

---

## License

Apache 2.0 — see the root [LICENSE](../../LICENSE) file.