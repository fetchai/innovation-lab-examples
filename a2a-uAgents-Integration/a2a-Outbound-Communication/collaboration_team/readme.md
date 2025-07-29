# Discussion Team Agent

## Description
The Discussion Team Agent is a collaborative AI system composed of specialized researchers (Reddit, HackerNews, Academic Paper, Twitter) that work together to provide comprehensive insights on a given topic from diverse online platforms.

## Purpose
To facilitate a holistic understanding of a topic by gathering and synthesizing information from social media discussions, tech news, and academic literature, ultimately reaching a consensus or comprehensive answer.

## Key Features
*   **Multi-Platform Research**: Gathers insights from Reddit, HackerNews, academic databases (Arxiv), and Twitter/X.
*   **Collaborative Discussion**: Agents share and discuss their findings to build a complete picture.
*   **Information Synthesis**: Combines diverse perspectives into a coherent and comprehensive answer.
*   **Academic Paper Links**: Provides direct links to Arxiv PDFs or pages for academic research, without downloading files.
*   **Consensus Building**: Aims to reach a well-rounded and agreed-upon conclusion.

## Usage Example
"Discuss the societal impact of large language models."

## Required Environment Variables
To run the Discussion Team Agent, you need to set the following environment variables in your `.env` file:

*   `OPENAI_API_KEY`: Your API key for OpenAI models (e.g., `gpt-4o`), used by all sub-agents and the team coordinator.
*   `GOOGLE_API_KEY`: Your API key for Google Search, used by the Academic Paper Researcher.
*   `GOOGLE_CSE_ID`: Your Custom Search Engine ID for Google Search, used by the Academic Paper Researcher.

Additionally, if you are using the `MultiA2AAdapter` for routing, you might need an API key for the routing LLM (e.g., `ASI1_API_KEY` if using `asi1.ai`).
