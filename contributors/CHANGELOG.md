# Contributors Changelog

All notable community-submitted agent examples are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `gemini-research-agent/`: Added Gemini-powered research assistant demonstrating the standard Agent Chat Protocol (@Kavurubuvanesh)
- `contributors/` folder and contribution guide for community agent examples
- `contributors/community_agent/` — moved from repository root; AI community growth agent for events and hackathons
- `contributors/cardiopulse-agent/` — live cardiovascular fitness-test agent that streams a Garmin watch's heart rate over BLE and runs a three-phase test through ASI:One
- `contributors/community_agent/` — moved from repository root; AI community growth agent for events and hackathons
### Fixed
- Fixed sandbox validation in `scan_directory` to properly reject paths outside the demo sandbox using `Path.relative_to()` (#159)
- `contributors/news-summarizer-agent/` — beginner-friendly agent that fetches top headlines via NewsAPI and summarizes them with ASI:One; now a uAgent with Chat Protocol support
