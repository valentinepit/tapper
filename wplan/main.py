import asyncio
import logging
from datetime import date, datetime

from src import settings
from src.api import WplanApiClient

logger = logging.getLogger(__name__)

# Между утренним (~10:00) и вечерним (~19:00) cron-запуском из README - середина
# дня, используется как граница, чтобы отличить "начать день" от "завершить день".
DAY_START_CUTOFF_HOUR = 14


async def run_api_flow():
    logger.info('Starting API flow')

    username = settings.WPLAN_LOGIN
    password = settings.WPLAN_PASS
    is_start = datetime.now().hour < DAY_START_CUTOFF_HOUR

    async with WplanApiClient() as client:
        logger.info(f'Logging in as {username}')
        user = await client.login(username, password)
        logger.info(f'Logged in as {user["fio"]}')

        logger.info('Fetching absences')
        today = date.today().isoformat()
        absences = await client.get_absences()
        logger.info(f'Fetched {len(absences)} absence record(s)')

        on_absence = any(a['startDate'] <= today <= a['endDate'] for a in absences)
        if on_absence:
            logger.info(f'{today} falls within an absence period - skipping start_end_workday')
            return

        logger.info(f'Calling start_end_workday(is_start={is_start})')
        result = await client.start_end_workday(is_start=is_start)
        logger.info(f'start_end_workday(is_start={is_start}) -> {result}')

    logger.info('Done')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(run_api_flow())


if __name__ == "__main__":
    main()
