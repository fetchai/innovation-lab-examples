import os
import requests
from dotenv import load_dotenv

load_dotenv()

load_dotenv()

ASI1_API_KEY = os.getenv("ASI1_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

NEWS_API_URL = "https://newsapi.org/v2/everything"
ASI1_API_URL = "https://api.asi1.ai/v1/chat/completions"


def fetch_headlines(topic: str) -> list[str]:
    """Fetch top 5 news headlines for a given topic using NewsAPI."""
    params = {
        "q": topic,
        "pageSize": 5,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": NEWS_API_KEY,
    }
    response = requests.get(NEWS_API_URL, params=params)
    response.raise_for_status()
    articles = response.json().get("articles", [])
    headlines = [a["title"] for a in articles if a.get("title")]
    return headlines


def summarize_with_asi1(topic: str, headlines: list[str]) -> str:
    """Send headlines to ASI:One LLM and get a readable summary."""
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = (
        f"Here are the top 5 recent news headlines about '{topic}':\n\n"
        f"{headlines_text}\n\n"
        f"Please write a short, clear, 3-4 sentence summary of what is "
        f"currently happening with '{topic}' based on these headlines."
    )

    headers = {
        "Authorization": f"Bearer {ASI1_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "asi1-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300,
        "stream": False,
    }

    response = requests.post(ASI1_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def run_agent(topic: str) -> None:
    """Main agent flow: fetch headlines then summarize."""
    print(f"\nFetching top headlines for topic: '{topic}'...")
    headlines = fetch_headlines(topic)

    if not headlines:
        print("No headlines found for this topic. Try a different one.")
        return

    print(f"\nFound {len(headlines)} headlines:")
    for h in headlines:
        print(f"  - {h}")

    print("\nSummarizing with ASI:One LLM...")
    summary = summarize_with_asi1(topic, headlines)

    print("\n--- Summary ---")
    print(summary)
    print("---------------\n")


if __name__ == "__main__":
    topic = input("Enter a topic to summarize news for (e.g. AI, climate, sports): ")
    run_agent(topic.strip())