# Contributors Changelog

All notable community-submitted agent examples are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `nano-xno-payment-agent/`: uAgents seller example that collects payment on the fee-less Nano (XNO) layer-1 via the payment protocol, with on-chain verification against the public Nano RPC
- `gemini-research-agent/`: Added Gemini-powered research assistant demonstrating the standard Agent Chat Protocol (@Kavurubuvanesh)
- `gemini-task-manager-agent/`: Added Gemini-powered task manager agent that breaks down user goals into actionable step-by-step plans using Google Gemini 2.0 Flash and uAgents Chat Protocol (@Bhargav-Devv)
- `contributors/` folder and contribution guide for community agent examples
- `contributors/community_agent/` — moved from repository root; AI community growth agent for events and hackathons
- `battle-training-bot/`: Added battle.training MCP agent — drives the arena's official MCP server (21 tools) to create/upload a tank-battle bot, run unrated scrimmages and report ladder results (@4ntonn)
### Fixed
- `nano-xno-payment-agent/`: the order-commitment account is now encoded like every Nano account (four zero bits on the high side), so it equals the `representative` a node returns in `block_info`; before, the representative check refused every honest bound payment
- Fixed sandbox validation in `scan_directory` to properly reject paths outside the demo sandbox using `Path.relative_to()` (#159)
- `contributors/news-summarizer-agent/` — beginner-friendly agent that fetches top headlines via NewsAPI and summarizes them with ASI:One; now a uAgent with Chat Protocol support
