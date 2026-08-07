import logging

import aiohttp

from src import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}) as resp:
                resp.raise_for_status()
    except Exception:
        logger.exception(f"Failed to send Telegram notification: {text!r}")
