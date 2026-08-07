import asyncio
import logging
from datetime import date, datetime

from src import settings
from src.api import WplanApiClient, WplanApiError

logger = logging.getLogger(__name__)


async def run_api_flow():
    logger.info('Starting API flow')

    username = settings.WPLAN_LOGIN
    password = settings.WPLAN_PASS
    is_start = datetime.now().hour < settings.DAY_START_CUTOFF_HOUR

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
        try:
            result = await client.start_end_workday(is_start=is_start)
        except WplanApiError as e:
            errors = e.args[0] if e.args else []
            if errors and errors[0].get('message') == 'EDITING_NOT_AVAILABLE':
                logger.info(f'Day already in the requested state (is_start={is_start}) - nothing to do')
                return
            raise
        logger.info(f'start_end_workday(is_start={is_start}) -> {result}')

    logger.info('Done')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(run_api_flow())


if __name__ == "__main__":
    main()
