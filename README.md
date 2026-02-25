# 📰 Newiz - AI News Bot

A smart, conversational Telegram bot that fetches the latest news, summarizes it using Google's Gemini AI, and provides high-quality audio briefings using OpenAI's TTS. 

## ✨ Features

- **🔍 Smart Search**: Get top news stories for any topic in seconds.
- **🤖 AI Summaries**: Uses Gemini 2.5 Flash to write concise, bulleted summaries of articles so you can read faster.
- **🗣️ Audio Briefings**: Listen to your news on the go! Uses OpenAI's `tts-1` (`nova` voice) for natural-sounding audio summaries.
- **🔥 Trending Topics**: Analyzes global headlines to automatically find the 5-7 hottest topics right now.
- **⏰ Scheduled Delivery**: Subscribe to your favorite topics and get a personalized news digest delivered to you automatically every day at your preferred time.
- **💬 Conversational UI**: Interactive menus, inline buttons, and conversational prompts make it easy to use.

## 🛠️ Tech Stack

- **Python 3.13**
- **[python-telegram-bot](https://python-telegram-bot.org/)**: For Telegram API integration.
- **[NewsAPI](https://newsapi.org/)**: To fetch global headlines and articles.
- **[Google Generative AI (Gemini)](https://aistudio.google.com/)**: For fast, intelligent article summarization and topic extraction.
- **[OpenAI API](https://platform.openai.com/)**: For premium Text-fo-Speech (TTS) generation.
- **APScheduler**: For handling daily scheduled briefs.
- **SQLite**: Lightweight local database to store user subscriptions and preferences.

## 🚀 Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/newsAI.git
   cd newsAI
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables:**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   NEWS_API_KEY=your_newsapi_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Run the bot:**
   ```bash
   python bot.py
   ```

## ☁️ Deployment (Koyeb Free Tier)

This bot is configured to run on [Koyeb's](https://www.koyeb.com/) Free Nano instance as a Web Service.

1. Create a new **Web Service** on Koyeb.
2. Connect your GitHub repository.
3. Choose the **Free - Nano** instance.
4. Add your 4 API keys in the **Environment Variables** section.
5. Deploy! (The `Procfile` and dummy web server in `bot.py` handle Koyeb's health checks automatically).

---
*Built with Python and AI.*
