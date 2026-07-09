# Contributors Changelog

All notable community-submitted agent examples are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **weather-monitor-agent** by [@AKIB2005](https://github.com/AKIB2005)
  - Beginner-friendly uAgent demonstrating chat protocol + REST API integration
  - Fetches live temperature, humidity, wind speed, and condition from OpenWeatherMap free tier
  - Configurable temperature alert threshold via `.env`
  - Registers on Agentverse; works with ASI:One chat out of the box
  - Zero cost barrier: no credit card required for OpenWeatherMap free tier
  - Closes [#131](https://github.com/fetchai/innovation-lab-examples/issues/131)
- `contributors/` folder and contribution guide for community agent examples
- `contributors/community_agent/` — moved from repository root; AI community growth agent for events and hackathons
- `gemini-research-agent/`: Added Gemini-powered research assistant demonstrating the standard Agent Chat Protocol (@Kavurubuvanesh)
- `gemini-task-manager-agent/`: Added Gemini-powered task manager agent that breaks down user goals into actionable step-by-step plans using Google Gemini 2.0 Flash and uAgents Chat Protocol (@Bhargav-Devv)
- `contributors/` folder and contribution guide for community agent examples
- `contributors/community_agent/` — moved from repository root; AI community growth agent for events and hackathons
### Fixed
- Fixed sandbox validation in `scan_directory` to properly reject paths outside the demo sandbox using `Path.relative_to()` (#159)
- `contributors/news-summarizer-agent/` — beginner-friendly agent that fetches top headlines via NewsAPI and summarizes them with ASI:One; now a uAgent with Chat Protocol support
