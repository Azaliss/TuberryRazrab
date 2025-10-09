import asyncio
import logging

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.bot import Bot
from app.models.dialog import Dialog
from app.services.telegram import TelegramService

LOGGER = logging.getLogger("tuberry.reset_topics")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

GENERAL_TOPIC_ID = 1


async def reset_bot_topics(bot: Bot) -> None:
    if not bot.group_chat_id or not bot.topic_mode:
        LOGGER.info("Bot %s skipped (no group chat or topic mode disabled)", bot.id)
        return

    tg = TelegramService(bot.token)
    removed = 0
    offset = None

    while True:
        try:
            response = await tg.get_forum_topic_list(bot.group_chat_id, offset=offset, limit=100)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Failed to fetch topic list for bot %s, attempting brute force cleanup: %s",
                bot.id,
                exc,
            )
            consecutive_failures = 0
            for topic_id in range(2, 1501):
                try:
                    await tg.delete_forum_topic(bot.group_chat_id, topic_id)
                    removed += 1
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures > 100:
                        break
            LOGGER.info("Bot %s: removed %d topics (brute force)", bot.id, removed)
            return

        topics = response.get("forum_topics") or []
        if not topics:
            break

        for topic in topics:
            topic_id = topic.get("message_thread_id")
            if topic_id == GENERAL_TOPIC_ID:
                continue
            try:
                await tg.delete_forum_topic(bot.group_chat_id, topic_id)
                removed += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to delete topic %s in chat %s: %s",
                    topic_id,
                    bot.group_chat_id,
                    exc,
                )
        # Telegram API does not document pagination behavior; break to avoid loops
        break

    LOGGER.info("Bot %s: removed %d topics", bot.id, removed)


async def reset_topics() -> None:
    async with SessionLocal() as session:
        bots = (await session.execute(select(Bot))).scalars().all()

    for bot in bots:
        await reset_bot_topics(bot)

    async with SessionLocal() as session:
        await session.execute(update(Dialog).values(telegram_topic_id=None))
        await session.commit()

    LOGGER.info("Dialog topic bindings cleared")


if __name__ == "__main__":
    asyncio.run(reset_topics())
