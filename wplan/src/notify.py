import logging

import aiohttp

from src import settings

logger = logging.getLogger(__name__)

# Отдельный таймаут: уведомление не должно задерживать завершение прогона.
NOTIFY_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)


async def send_telegram_message(text: str) -> None:
    """
    Отправить уведомление в Telegram.
    """
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}
    try:
        async with aiohttp.ClientSession(timeout=NOTIFY_TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    logger.error("Telegram API вернул HTTP %s", resp.status)
    except aiohttp.ClientError as e:
        logger.error("Не удалось отправить уведомление: %s", type(e).__name__)
    except Exception as e:  # noqa: BLE001 - намеренно широкий: уведомление не должно ронять прогон
        logger.error("Не удалось отправить уведомление: %s", type(e).__name__)
