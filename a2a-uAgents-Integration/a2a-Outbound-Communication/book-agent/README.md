# Books Recommender Agent

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![a2a](https://img.shields.io/badge/a2a-000000) ![agno](https://img.shields.io/badge/agno-FF69B4) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4)

## 📚 Books Recommender Agent: Your Intelligent Reading Companion

Struggling to find the next great read amid endless options? The Books Recommender Agent is your AI-powered personal librarian, designed to curate books that perfectly align with your tastes. Using advanced AI and web search tools, this agent delivers tailored book suggestions with comprehensive details and insightful comparisons to enhance your reading experience.

### What it Does
This agent helps you quickly find your next book without the hassle. Tell it what you like, and it suggests matching titles with clear info and links from trusted places.

## ✨ Key Features

* Personalized picks based on what you like
* Uses trusted sites like Amazon, Goodreads, and Google Books
* Checks that books are available now
* Clear details: title, author, price, rating, format, summary, and link
* Quick comparisons to help you decide


## 🔧 Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd book-agent
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

Create a `.env` file in the project root directory with the following variables:

```env
# Google AI API Key (required for Gemini model)
GOOGLE_API_KEY=your_google_api_key_here

# Exa API Key (required for web search functionality)
EXA_API_KEY=your_exa_api_key_here
```

**How to get API keys:**
- **Google API Key**: Get it from [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Exa API Key**: Sign up at [Exa.ai Dashboard](https://dashboard.exa.ai/)

### How to Start

Run the application with:

```bash
python main.py
```

**To stop the application:** Press `CTRL+C` in the terminal

### Example Query

```plaintext
Recommend up to 5 science fiction books with strong world-building, published after 2015, available on Amazon or Goodreads, preferably under $20 in ebook format.
```

### Expected Output (Example Snippet)

```markdown
# Book Recommendations for Science Fiction

## 1. The Three-Body Problem
- **Author(s):** Cixin Liu
- **Link:** [https://www.amazon.com/three-body-problem-link](https://www.amazon.com/three-body-problem-link)
- **Price:** $9.99 USD (ebook)
- **Average Rating:** 4.1/5 stars (based on 50,000+ reviews on Goodreads)
- **Key Details:** Genre: Science Fiction, Publication Date: 2014 (English edition), Page Count: 400, Format: Ebook
- **Summary:** A secret military project in China sends signals into space to establish contact with aliens, leading to profound consequences for humanity.
- **Pros:** Incredible world-building, thought-provoking concepts, gripping plot.
- **Cons:** Some find the translation awkward, dense scientific explanations.
- **Availability:** Available for Purchase

## 2. Project Hail Mary
- **Author(s):** Andy Weir
- **Link:** [https://www.goodreads.com/project-hail-mary-link](https://www.goodreads.com/project-hail-mary-link)
- **Price:** $14.99 USD (ebook)
- **Average Rating:** 4.5/5 stars (based on 200,000+ reviews on Goodreads)
- **Key Details:** Genre: Science Fiction, Publication Date: 2021, Page Count: 496, Format: Ebook
- **Summary:** A lone astronaut must figure out how to save Earth from disaster, facing interstellar challenges with science and ingenuity.
- **Pros:** Engaging storytelling, hard science elements, humorous narrative.
- **Cons:** Predictable in parts, heavy on technical details.
- **Availability:** Available for Purchase

... (up to 10 detailed book recommendations) ...

## 📊 Comparative Analysis (Top 3)

| Feature             | The Three-Body Problem | Project Hail Mary | Dune Messiah      |
|---------------------|------------------------|-------------------|-------------------|
| **Price**           | $9.99                  | $14.99            | $12.99            |
| **Publication Year**| 2014                   | 2021              | 1969 (reprint)    |
| **Rating**          | 4.1/5                  | 4.5/5             | 3.9/5             |
| **World-Building** | Exceptional            | Strong            | Iconic            |
| **Best For**        | Philosophical sci-fi   | Adventure & science | Epic sagas        |
```


## 🧠 Inspired by

* [Fetch.ai uAgents](https://github.com/fetchai/uAgents)
* [Agno Framework](https://github.com/agnos-ai/agno)
* [A2A Protocol](https://a2a-protocol.org/latest/)
* [Fetch.ai Innovation Lab Examples](https://github.com/fetchai/innovation-lab-examples)