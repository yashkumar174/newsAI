import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from database import (
    init_db, add_topic, remove_topic, get_user_topics,
    clear_topics, set_user_timezone, get_user_settings, ensure_user
)
from scheduler import start_scheduler
from news_engine import get_daily_summary, get_trending_topics
from tts_engine import text_to_speech, cleanup_audio
import pytz

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory store for last search per chat (for button callbacks)
last_search = {}

# Conversation states
WAITING_NEWS_TOPIC, WAITING_VOICE_TOPIC, WAITING_TOPIC_ADD = range(3)


# ─── COMMANDS ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    await update.message.reply_text(
        "👋 *Welcome to your Personal News Bot!*\n\n"
        "*Commands:*\n"
        "📰 `/news <topic>` — Top 3 stories instantly\n"
        "📰 `/news <count> <topic>` — Choose how many (e.g. `/news 5 AI`)\n\n"
        "🗣️ `/voice <topic>` — Listen to the news as audio\n\n"
        "📌 `/topic add <topic>` — Subscribe to a topic\n"
        "📌 `/topic remove <topic>` — Unsubscribe\n"
        "📌 `/topic list` — See your subscriptions\n"
        "📌 `/topic clear` — Remove all subscriptions\n\n"
        "⏰ `/time <HH:MM> <timezone>` — Set your daily delivery time\n"
        "    Example: `/time 09:00 Asia/Kolkata`\n\n"
        "🔥 `/trending` — See what topics are hot globally right now\n\n"
        "🚨 Breaking alerts are sent automatically when big news matches your topics (max 3/day).",
        parse_mode="Markdown"
    )


async def get_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("📰 What topic do you want news about?\n\n_You can also include a number for how many stories (e.g. `5 python`)_", parse_mode="Markdown")
        return WAITING_NEWS_TOPIC

    # Parse optional count
    count = 3
    if context.args[0].isdigit():
        count = min(int(context.args[0]), 10)
        topic_args = context.args[1:]
    else:
        topic_args = context.args

    if not topic_args:
        await update.message.reply_text(
            "Please provide a topic after the number.\nExample: `/news 5 python`",
            parse_mode="Markdown"
        )
        return

    topic = " ".join(topic_args)
    chat_id = update.effective_chat.id
    last_search[chat_id] = {"topic": topic, "count": count, "page": 1}

    await update.message.reply_text(
        f"🔍 Fetching top {count} stories for *{topic}*... please wait.",
        parse_mode="Markdown"
    )

    summary = get_daily_summary(topic, count)

    # Build inline keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 More Stories", callback_data="more_stories"),
            InlineKeyboardButton("🗣️ Read Aloud", callback_data="read_aloud"),
        ],
        [
            InlineKeyboardButton("⚙️ Save Topic", callback_data="save_topic"),
        ]
    ])

    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)
    return ConversationHandler.END


async def news_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's reply when they tapped /news from menu."""
    text = update.message.text.strip()
    context.args = text.split()
    return await get_news(update, context)


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("🗣️ What topic do you want to listen to?")
        return WAITING_VOICE_TOPIC

    topic = " ".join(context.args)
    await update.message.reply_text(
        f"🎙️ Generating audio summary for *{topic}*... this may take a moment.",
        parse_mode="Markdown"
    )

    summary = get_daily_summary(topic, count=3)
    audio_path = None
    try:
        audio_path = text_to_speech(summary)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        await update.message.reply_text("Sorry, failed to generate audio. Here's the text version:")
        await update.message.reply_text(summary, parse_mode="Markdown")
        return

    try:
        with open(audio_path, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file, caption=f"🗣️ News summary for: {topic}")
    except Exception as e:
        logger.error(f"TTS send error: {e}")
        await update.message.reply_text("Sorry, failed to send audio.")
    finally:
        cleanup_audio(audio_path)
    return ConversationHandler.END


async def voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's reply when they tapped /voice from menu."""
    context.args = update.message.text.strip().split()
    return await voice_command(update, context)


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    ensure_user(chat_id)

    if not context.args:
        await update.message.reply_text(
            "📌 What topic do you want to subscribe to?\n\n"
            "_Or type a command like `add python`, `remove AI`, `list`, or `clear`_",
            parse_mode="Markdown"
        )
        return WAITING_TOPIC_ADD

    action = context.args[0].lower()

    if action == "add":
        if len(context.args) < 2:
            await update.message.reply_text("Please provide a topic. Example: `/topic add python`", parse_mode="Markdown")
            return
        topic = " ".join(context.args[1:])
        add_topic(chat_id, topic)
        topics = get_user_topics(chat_id)
        await update.message.reply_text(
            f"✅ Subscribed to: *{topic}*\n\n"
            f"Your topics ({len(topics)}): {', '.join(topics)}",
            parse_mode="Markdown"
        )

    elif action == "remove":
        if len(context.args) < 2:
            await update.message.reply_text("Please provide a topic. Example: `/topic remove python`", parse_mode="Markdown")
            return
        topic = " ".join(context.args[1:])
        remove_topic(chat_id, topic)
        topics = get_user_topics(chat_id)
        topic_list = ', '.join(topics) if topics else 'None'
        await update.message.reply_text(
            f"🗑️ Unsubscribed from: *{topic}*\n\n"
            f"Your topics ({len(topics)}): {topic_list}",
            parse_mode="Markdown"
        )

    elif action == "list":
        topics = get_user_topics(chat_id)
        if topics:
            topic_lines = "\n".join([f"  • {t}" for t in topics])
            await update.message.reply_text(
                f"📌 *Your subscribed topics ({len(topics)}):*\n{topic_lines}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("You have no subscribed topics. Use `/topic add <topic>` to add one.", parse_mode="Markdown")

    elif action == "clear":
        clear_topics(chat_id)
        await update.message.reply_text("🗑️ All topics removed.", parse_mode="Markdown")

    else:
        # If user types /topic python (old behavior), treat as "add"
        topic = " ".join(context.args)
        add_topic(chat_id, topic)
        topics = get_user_topics(chat_id)
        await update.message.reply_text(
            f"✅ Subscribed to: *{topic}*\n\n"
            f"Your topics ({len(topics)}): {', '.join(topics)}",
            parse_mode="Markdown"
        )

    return ConversationHandler.END


async def topic_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's reply when they tapped /topic from menu."""
    text = update.message.text.strip()
    context.args = text.split()
    return await topic_command(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Use /start to see all commands.")
    return ConversationHandler.END


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    ensure_user(chat_id)

    if not context.args or len(context.args) < 2:
        settings = get_user_settings(chat_id)
        await update.message.reply_text(
            f"*Current schedule:* {settings[1]}:00 ({settings[0]})\n\n"
            f"To change: `/time HH:MM Timezone`\n"
            f"Example: `/time 09:00 Asia/Kolkata`\n\n"
            f"Common timezones:\n"
            f"• `Asia/Kolkata` (IST)\n"
            f"• `America/New_York` (EST)\n"
            f"• `Europe/London` (GMT)\n"
            f"• `Asia/Tokyo` (JST)\n"
            f"• `US/Pacific` (PST)",
            parse_mode="Markdown"
        )
        return

    time_str = context.args[0]
    tz_str = context.args[1]

    # Parse time
    try:
        hour = int(time_str.split(":")[0])
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Invalid time format. Please use HH:MM (e.g., `09:00`).", parse_mode="Markdown")
        return

    # Validate timezone
    if tz_str not in pytz.all_timezones:
        await update.message.reply_text(
            f"Unknown timezone: `{tz_str}`\n\n"
            f"Try common ones like `Asia/Kolkata`, `America/New_York`, `Europe/London`.",
            parse_mode="Markdown"
        )
        return

    set_user_timezone(chat_id, tz_str, hour)
    await update.message.reply_text(
        f"✅ Daily news set for *{hour:02d}:00* ({tz_str})",
        parse_mode="Markdown"
    )


# ─── INLINE BUTTON CALLBACKS ──────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data

    search_data = last_search.get(chat_id)
    if not search_data:
        await query.message.reply_text("No recent search found. Please use `/news <topic>` first.", parse_mode="Markdown")
        return

    topic = search_data["topic"]
    count = search_data.get("count", 3)

    if data == "more_stories":
        page = search_data.get("page", 1) + 1
        last_search[chat_id]["page"] = page
        await query.message.reply_text(f"🔄 Fetching page {page} for *{topic}*...", parse_mode="Markdown")
        summary = get_daily_summary(topic, count, page=page)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 More Stories", callback_data="more_stories"),
                InlineKeyboardButton("🗣️ Read Aloud", callback_data="read_aloud"),
            ],
            [
                InlineKeyboardButton("⚙️ Save Topic", callback_data="save_topic"),
            ]
        ])
        await query.message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)

    elif data == "read_aloud":
        await query.message.reply_text("🎙️ Converting to audio... please wait.")

        summary = get_daily_summary(topic, count)
        audio_path = None
        try:
            audio_path = text_to_speech(summary)
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            await query.message.reply_text("Sorry, failed to generate audio.")
            return

        try:
            with open(audio_path, 'rb') as audio_file:
                await query.message.reply_voice(voice=audio_file, caption=f"🗣️ News for: {topic}")
        except Exception as e:
            logger.error(f"TTS send error: {e}")
            await query.message.reply_text("Sorry, failed to send audio.")
        finally:
            cleanup_audio(audio_path)

    elif data == "save_topic":
        add_topic(chat_id, topic)
        topics = get_user_topics(chat_id)
        await query.message.reply_text(
            f"⚙️ Saved *{topic}* to your daily subscriptions!\n\n"
            f"Your topics ({len(topics)}): {', '.join(topics)}",
            parse_mode="Markdown"
        )


async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔥 Analyzing global headlines... please wait.")

    result = get_trending_topics()
    await update.message.reply_text(result, parse_mode="Markdown")


# ─── ENTRY POINT ──────────────────────────────────────────

async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Show welcome message and all commands"),
        BotCommand("news", "Get top news stories for a topic"),
        BotCommand("voice", "Listen to news as audio"),
        BotCommand("topic", "Manage your topic subscriptions"),
        BotCommand("time", "Set your daily delivery time & timezone"),
        BotCommand("trending", "See what topics are hot right now"),
    ])
    await start_scheduler(application)


class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, DummyServer)
    httpd.serve_forever()

def main():
    init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables.")

    application = Application.builder().token(token).post_init(post_init).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("trending", trending_command))

    # Conversation handlers (prompt for input when no args)
    news_conv = ConversationHandler(
        entry_points=[CommandHandler("news", get_news)],
        states={WAITING_NEWS_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, news_reply)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    voice_conv = ConversationHandler(
        entry_points=[CommandHandler("voice", voice_command)],
        states={WAITING_VOICE_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, voice_reply)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    topic_conv = ConversationHandler(
        entry_points=[CommandHandler("topic", topic_command)],
        states={WAITING_TOPIC_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, topic_reply)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(news_conv)
    application.add_handler(voice_conv)
    application.add_handler(topic_conv)

    # Inline button handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start dummy web server for health checks
    threading.Thread(target=run_dummy_server, daemon=True).start()

    logger.info("Bot starting with all features enabled...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
