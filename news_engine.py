import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


def filter_articles(articles: list) -> list:
    filtered = []
    for art in articles:
        if art.get("title") == "[Removed]":
            continue
        desc = art.get("description")
        if not desc or len(desc) < 30:
            continue
        filtered.append({"title": art.get("title"), "description": desc, "url": art.get("url")})
    return filtered[:10]


def format_for_prompt(articles: list) -> str:
    return json.dumps([{"id": i, "title": a["title"], "desc": a["description"]} for i, a in enumerate(articles)])


def get_daily_summary(topic: str, count: int = 3, page: int = 1) -> str:
    news_api_key = os.getenv("NEWS_API_KEY")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # 1. Fetch News (paginated)
    url = f"https://newsapi.org/v2/everything?q={topic}&language=en&sortBy=relevance&page={page}&pageSize=10&apiKey={news_api_key}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return f"Error fetching news for {topic}."

    articles = resp.json().get("articles", [])
    filtered = filter_articles(articles)

    if not filtered:
        return f"No relevant news found today for the topic: {topic}."

    # Build article data with URLs for the prompt
    articles_with_urls = json.dumps([
        {"id": i, "title": a["title"], "desc": a["description"], "url": a.get("url", "")}
        for i, a in enumerate(filtered)
    ])

    # 2. Summarize with LLM
    prompt = f"""
You are a professional daily news briefer for Telegram.
Here are the top headlines for the topic: '{topic}'.
{articles_with_urls}

Select the {count} most important/relevant stories from this list.
Format the output EXACTLY like this numbered list (use Telegram-compatible markdown):

*1. Headline here*
A concise 2-sentence summary of this story.
🔗 Source: URL_HERE

*2. Headline here*
A concise 2-sentence summary of this story.
🔗 Source: URL_HERE

Rules:
- Use *bold* (single asterisks) for headlines — NOT **double asterisks**
- Each story gets a number, bold headline, 2-sentence summary, and source URL on its own line
- Keep summaries extremely concise
- Do NOT add any extra sections, headers, or footers
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


def get_trending_summary() -> str:
    news_api_key = os.getenv("NEWS_API_KEY")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Fetch top headlines
    url = f"https://newsapi.org/v2/top-headlines?language=en&country=us&apiKey={news_api_key}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return "Error fetching trending news."

    articles = resp.json().get("articles", [])
    filtered = filter_articles(articles)

    if not filtered:
        return "No trending news found today."

    articles_with_urls = json.dumps([
        {"id": i, "title": a["title"], "desc": a["description"], "url": a.get("url", "")}
        for i, a in enumerate(filtered)
    ])

    prompt = f"""
You are a professional daily news briefer for Telegram.
Here are today's top trending headlines.
{articles_with_urls}

Select the 3 most important/relevant stories from this list.
Start with a "☀️ Good morning!" greeting line.
Format the output EXACTLY like this numbered list (use Telegram-compatible markdown):

*1. Headline here*
A concise 2-sentence summary of this story.
🔗 Source: URL_HERE

*2. Headline here*
A concise 2-sentence summary of this story.
🔗 Source: URL_HERE

Rules:
- Use *bold* (single asterisks) for headlines — NOT **double asterisks**
- Each story gets a number, bold headline, 2-sentence summary, and source URL on its own line
- Keep summaries extremely concise
- Do NOT add any extra sections, headers, or footers
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


def get_trending_topics() -> str:
    """Analyze top headlines to identify trending topics globally."""
    news_api_key = os.getenv("NEWS_API_KEY")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Fetch top headlines from multiple categories
    all_articles = []
    for category in ["general", "technology", "business", "science", "health"]:
        url = f"https://newsapi.org/v2/top-headlines?language=en&country=us&category={category}&apiKey={news_api_key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                all_articles.extend(articles)
        except requests.RequestException:
            continue

    filtered = filter_articles(all_articles)

    if not filtered:
        return "Could not fetch trending topics right now. Try again later."

    articles_data = json.dumps([
        {"title": a["title"], "desc": a["description"]}
        for a in filtered
    ])

    prompt = f"""
You are a trend analyst. Analyze these headlines and identify the hottest trending topics right now.
{articles_data}

Extract 5-7 distinct trending topics/themes from these headlines.
Format EXACTLY like this (Telegram-compatible markdown):

🔥 *Trending Topics Right Now*

*1. Topic Name*
Brief 1-line explanation of why this is trending.

*2. Topic Name*
Brief 1-line explanation of why this is trending.

... and so on.

At the end, add this line:
💡 _Use /news <topic> to dive deeper into any of these!_

Rules:
- Use *bold* (single asterisks) for topic names
- Keep explanations to ONE concise line each
- Group similar headlines into a single topic
- Order by how "hot" the topic is (most trending first)
- Do NOT use **double asterisks**
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text

