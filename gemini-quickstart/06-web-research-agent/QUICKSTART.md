# ⚡ 5-Minute Quick Start - Web Research Agent

Research any URL with AI in minutes!

## 1️⃣ Setup (1 minute)

```bash
cd 06-web-research-agent

# Use existing venv
pip install -r requirements.txt

# Use same .env - already have GEMINI_API_KEY!
```

## 2️⃣ Run (30 seconds)

```bash
python research_agent.py
```

## 3️⃣ Test (30 seconds)

**Via ASI One:**
1. Find your agent
2. Send a URL with a question
3. Get AI-powered analysis!

## 4️⃣ Try These Prompts

### Format 1: URL + Question
```
https://ai.google.dev - What are the latest updates?
```

### Format 2: Explicit Format
```
URL: https://news.ycombinator.com
Question: What are today's top stories?
```

### Format 3: Analysis Request
```
https://techcrunch.com/article - Summarize this article
```

### More Examples:
```
https://github.com/trending - What are the trending repositories today?
```

```
https://ai.google.dev/gemini-api/docs/changelog - What are the top 3 recent announcements?
```

```
https://wikipedia.org/wiki/Artificial_intelligence - Explain the key concepts
```

## 🔍 What It Can Do

- **Summarize** articles and web pages
- **Extract** key information
- **Answer** specific questions about content
- **Analyze** data and trends
- **Compare** information across pages
- **Fact-check** claims

## 📝 Input Formats

### Option 1: Natural
```
<url> - <question>
```

### Option 2: Structured
```
URL: <url>
Question: <question>
```

### Option 3: Just URL
```
<url>
(Automatically summarizes)
```

## 💡 Tips

1. **Be Specific** - Ask clear questions
2. **Public URLs** - Agent can only access public pages
3. **Recent Content** - Works best with accessible web pages
4. **No Auth Required** - Can't access pages requiring login

## 🚫 Limitations

- Cannot access pages behind authentication
- Cannot access private/internal networks
- Cannot execute JavaScript (gets rendered HTML)
- Rate limits may apply for heavy usage

## 🎯 Use Cases

- **News Summaries** - Get key points from articles
- **Documentation** - Extract info from docs
- **Research** - Gather information from multiple sources
- **Competitor Analysis** - Analyze competitor websites
- **Content Review** - Check what's on a page
- **Fact Checking** - Verify information

## ✅ Done!

You now have an AI web research assistant! 🔍✨

**Note:** This agent returns TEXT responses (no file generation).
