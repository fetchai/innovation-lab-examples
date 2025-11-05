# Discussion Team Agent

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![agno](https://img.shields.io/badge/agno-FF69B4) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4)

## 🎯 Discussion Team Agent: Your AI-Powered Research Collaboration Partner

Need comprehensive research on any topic from multiple perspectives? The Discussion Team Agent is your AI-powered research collaboration system, designed to gather insights from diverse online platforms and synthesize them into comprehensive, well-structured analysis. Using advanced AI agents working together, this system delivers detailed research with structured tables, direct links, and balanced perspectives to give you a complete understanding of any topic.

### What it Does

This agent helps you quickly understand complex topics by gathering insights from Reddit discussions, HackerNews technical discussions, academic research papers, and Twitter trending conversations. All agents work together to provide a holistic view with detailed analysis and actionable insights.

## ✨ Key Features

* **Multi-Platform Research** - Gathers insights from Reddit, HackerNews, academic databases, and Twitter/X
* **Collaborative AI Agents** - Four specialized researchers work together simultaneously
* **Structured Analysis** - Comprehensive tables, direct links, and organized findings
* **Balanced Perspectives** - Both positive and negative viewpoints with quantitative data
* **Academic Integration** - Direct links to research papers and scholarly sources
* **Real-Time Insights** - Current discussions and trending topics from social platforms

## 🔧 Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Google API key for Gemini

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd collaboration_team
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# Google API Key (required for Gemini 2.0 Flash model)
GOOGLE_API_KEY=your_google_api_key_here
```

**How to get API keys:**
- **Google API Key**: Get it from [Google AI Studio](https://aistudio.google.com/app/apikey)

### How to Start

Run the application with:

```bash
python main.py
```

The agent will start on the following ports:
- **Discussion Team Specialist**: `http://localhost:10020`
- **uAgent Coordinator**: `http://localhost:8200`

**To stop the application:** Press `CTRL+C` in the terminal

### Example Query

```plaintext
Discuss the societal impact of large language models.
```

### Expected Output Structure

```markdown
# Societal Impact of Large Language Models: Comprehensive Analysis

## Executive Summary
[2-3 paragraph overview of key findings]

## Detailed Findings by Platform

### Reddit Community Discussions
[Community insights with summary table]

### HackerNews Technical Analysis  
[Technical insights with summary table]

| Post Title | Points | Comments | Technical Focus | Industry Impact | Key Insight |
|------------|--------|----------|-----------------|-----------------|-------------|

### Academic Research Analysis
[Research findings with summary table]

| Paper Title | Authors | Publication | Year | Citations | Key Finding | Direct Link |
|-------------|---------|-------------|------|-----------|-------------|-------------|

### Twitter/X Trending Analysis
[Social media insights with summary table]

| Username | Followers | Tweet Content | Engagement | Sentiment | Key Point | Direct Link |
|----------|-----------|---------------|------------|-----------|-----------|-------------|

## Cross-Platform Analysis
[Comparison and synthesis tables]

## Impact Assessment
[Positive/Negative impacts in table format]

## Recommendations
[Actionable insights and strategies]

## Conclusion
[Summary of key takeaways]
```

## 🧠 Agent Team Composition

### 1. Reddit Researcher
- **Focus**: Community discussions and popular opinions
- **Tools**: DuckDuckGo search for Reddit content
- **Output**: Community insights, common opinions, discussion trends
- **Mandatory**: Summary of key insights from Reddit discussions

### 2. HackerNews Researcher  
- **Focus**: Technical discussions and industry insights
- **Tools**: HackerNews API integration
- **Output**: Technical deep-dives, industry implications, expert opinions
- **Mandatory**: Summary table with direct links to HN posts

### 3. Academic Paper Researcher
- **Focus**: Scholarly research and academic literature
- **Tools**: Google Search + Arxiv tools
- **Output**: Research papers, methodology analysis, citation data
- **Mandatory**: Summary table with direct links to PDFs/papers

### 4. Twitter Researcher
- **Focus**: Real-time trends and social media discussions
- **Tools**: DuckDuckGo search for Twitter content
- **Output**: Trending topics, influencer perspectives, viral discussions
- **Mandatory**: Summary table with direct links to tweets

## 📊 Usage Examples

### Basic Research Query
```
"Discuss the future of renewable energy"
```

### Specific Topic Analysis
```
"Analyze the impact of social media on mental health"
```

### Industry Research
```
"Research the competitive landscape of electric vehicles"
```

### Academic Topic Exploration
```
"Explore recent developments in quantum computing"
```

## 🔧 Technical Architecture

- **Framework**: uAgents + A2A Protocol + Agno Framework
- **AI Models**: Google Gemini 2.0 Flash
- **Communication**: Asynchronous agent collaboration
- **Data Sources**: Multi-platform web scraping and API integration
- **Output Format**: Markdown with tables, links, and structured analysis

## 🆘 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure your Google API key is correctly set in the `.env` file
2. **Port Conflicts**: Check if ports 10020, 8200, or 9999 are already in use. Kill them with:
   ```bash
   lsof -ti:10020,8200,9999 | xargs kill -9
   ```
3. **Dependency Issues**: Run `pip install -r requirements.txt` to ensure all packages are installed
4. **Google API Limits**: If you hit rate limits, wait a few moments or upgrade your API plan

### Performance Tips

- The agent works best with specific, focused queries
- Complex topics may take longer to research (up to 10 minutes timeout set)
- Ensure stable internet connection for optimal performance

## 📈 Future Enhancements

- [ ] Additional research platforms (LinkedIn, Medium, etc.)
- [ ] Enhanced table generation and formatting
- [ ] Export functionality (PDF, Word, Excel)
- [ ] Custom research templates
- [ ] Multi-language support
- [ ] Advanced filtering and search options

## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [Agno Framework](https://github.com/agnos-ai/agno)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)
