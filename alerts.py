import os
import logging
import requests
from dotenv import load_dotenv
from news_engine import filter_articles

load_dotenv()
logger = logging.getLogger(__name__)


def check_breaking_news(topics: list) -> list:
    """
    Check NewsAPI top-headlines for articles matching any of the user's topics.
    Returns a list of matching articles with their matched topic.
    """
    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key:
        logger.error("NEWS_API_KEY not set.")
        return []

    # Fetch top headlines
    url = f"https://newsapi.org/v2/top-headlines?language=en&country=us&apiKey={news_api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logger.error(f"NewsAPI returned status {resp.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Failed to fetch breaking news: {e}")
        return []

    articles = resp.json().get("articles", [])
    filtered = filter_articles(articles)

    if not filtered:
        return []

    # Match articles against user's topics using keyword matching
    matches = []
    for article in filtered:
        title = (article.get("title") or "").lower()
        desc = (article.get("description") or "").lower()
        combined = f"{title} {desc}"

        for topic in topics:
            keywords = topic.lower().split()
            # An article matches if ALL keywords of a topic appear in title or description
            if all(kw in combined for kw in keywords):
                matches.append({
                    "topic": topic,
                    "title": article["title"],
                    "description": article["description"],
                    "url": article.get("url", "")
                })
                break  # Don't double-match same article

    return matches[:3]  # Return at most 3 matches


def format_breaking_alert(matches: list) -> str:
    """Format breaking news matches into a Telegram-friendly alert message."""
    if not matches:
        return ""

    lines = ["🚨 *Breaking News Alert!*\n"]
    for i, m in enumerate(matches, 1):
        lines.append(f"*{i}. {m['title']}*")
        lines.append(f"{m['description']}")
        lines.append(f"🔗 {m['url']}\n")

    return "\n".join(lines)
