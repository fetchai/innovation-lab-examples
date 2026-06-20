# Hackrawl — Hackathon Discovery & Registration Agent

## Overview

An AI agent that helps you find, explore, and register for hackathons across the world. Powered by ASI:One and backed by a live database of 16,700+ events from 7 major platforms.

## What It Does

- **Discover** — search across Cerebral Valley, Devpost, MLH, ETHGlobal, DoraHacks, and more
- **Recommend** — ranked results tailored to your interests, location, and tech stack
- **Explore** — full event details: dates, prizes, tracks, sponsors, registration questions
- **Register** — auto-fills registration forms using your profile via browser automation

## How to Use

Just send a message describing what you're looking for:

### Find Hackathons
```
Find AI hackathons in San Francisco next month
Show me online hackathons with prizes over $10k
ETHGlobal and Web3 hackathons coming up
Hackathons for ML engineers this summer
```

### Event Details
```
Tell me about the AIEWF hackathon 2026
What are the details for the Machina Hackathon?
What's the prize for the RAISE Summit Hackathon?
```

### Statistics
```
How many hackathons are on Devpost?
Which platforms have the most upcoming events?
How many hackathons have cash prizes?
```

### Registration
Click **Register Now** on any event card to start automated registration.

## Supported Platforms

| Platform | Events |
|---|---|
| Devpost | 13,472 |
| Cerebral Valley | 2,710 |
| MLH | 413 |
| ETHGlobal | 84 |
| DoraHacks | 24 |
| HackerEarth | 13 |
| Devfolio | 4 |

## Tech Stack

- **ASI:One** (asi1-mini) — intent parsing, answer generation, LLM reranking
- **Supabase** — 16,700+ event database with full-text search
- **browser-use** — browser automation for registration
- **Playwright** — platform-specific form handling
- **uAgents** — Fetch.ai agent framework
- **crawl4ai** — web crawling with JS rendering

## Data Freshness

Events are crawled regularly. The database includes past and upcoming events dating back to 2024.

## Privacy

Your registration profile is stored locally on your machine (`~/.hackathon_profile.json`). No personal data is sent to external services beyond what's needed for each registration form.

---

**Built with** ASI:One + Fetch.ai uAgents + crawl4ai  
**Agent name**: Hackrawl
