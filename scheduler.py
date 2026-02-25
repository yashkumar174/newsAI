import logging
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from database import get_all_users_with_topics, get_all_users, get_user_topics, get_alert_count, increment_alert_count
from news_engine import get_daily_summary, get_trending_summary
from alerts import check_breaking_news, format_breaking_alert

logger = logging.getLogger(__name__)

MAX_ALERTS_PER_DAY = 3


async def send_scheduled_summaries(application: Application):
    """
    Runs every hour. For each user, checks if the current hour in their timezone
    matches their preferred schedule_hour. If so, sends personalized topic summaries.
    """
    logger.info("Checking scheduled summaries...")
    users = get_all_users_with_topics()

    if not users:
        logger.info("No users with topics, skipping.")
        return

    for chat_id, tz_name, schedule_hour, topics in users:
        try:
            user_tz = pytz.timezone(tz_name)
            now_user = datetime.now(user_tz)

            if now_user.hour != schedule_hour:
                continue

            logger.info(f"Sending scheduled summary to {chat_id} ({tz_name}, hour={schedule_hour})")

            # Send trending news first
            trending = get_trending_summary()
            await application.bot.send_message(chat_id=chat_id, text="☀️ *Good Morning! Here's your daily briefing:*", parse_mode="Markdown")
            await application.bot.send_message(chat_id=chat_id, text=trending, parse_mode="Markdown")

            # Then send per-topic summaries
            for topic in topics:
                summary = get_daily_summary(topic, count=3)
                header = f"📰 *Your topic: {topic}*\n\n"
                await application.bot.send_message(chat_id=chat_id, text=header + summary, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Failed to send scheduled summary to {chat_id}: {e}")


async def check_breaking_alerts(application: Application):
    """
    Runs every hour. Checks for breaking news matching each user's topics.
    Sends at most MAX_ALERTS_PER_DAY alerts per user per day.
    """
    logger.info("Checking breaking news alerts...")
    all_users = get_all_users()

    for chat_id, tz_name, _ in all_users:
        try:
            # Check daily alert limit
            today = datetime.utcnow().strftime('%Y-%m-%d')
            count = get_alert_count(chat_id, today)
            if count >= MAX_ALERTS_PER_DAY:
                continue

            topics = get_user_topics(chat_id)
            if not topics:
                continue

            matches = check_breaking_news(topics)
            if not matches:
                continue

            # Only send as many alerts as the remaining daily allowance
            remaining = MAX_ALERTS_PER_DAY - count
            matches = matches[:remaining]

            alert_text = format_breaking_alert(matches)
            if alert_text:
                await application.bot.send_message(chat_id=chat_id, text=alert_text, parse_mode="Markdown")
                increment_alert_count(chat_id, today)
                logger.info(f"Sent breaking alert to {chat_id} ({len(matches)} stories)")

        except Exception as e:
            logger.error(f"Failed to check alerts for {chat_id}: {e}")


async def start_scheduler(application: Application):
    scheduler = AsyncIOScheduler()

    # Check scheduled summaries every hour (at minute 0)
    scheduler.add_job(send_scheduled_summaries, 'cron', minute=0, args=[application], id='scheduled_summaries')

    # Check breaking news every hour (at minute 30, offset from summaries)
    scheduler.add_job(check_breaking_alerts, 'cron', minute=30, args=[application], id='breaking_alerts')

    scheduler.start()
    logger.info("Scheduler started. Hourly checks for summaries and breaking alerts.")
