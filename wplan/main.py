import asyncio
import logging
from datetime import date, datetime

# from src.driver import BrowserManager
# from src.actions import actions
from src import settings
from src.api import WplanApiClient

logger = logging.getLogger(__name__)

# Между утренним (~10:00) и вечерним (~19:00) cron-запуском из README - середина
# дня, используется как граница, чтобы отличить "начать день" от "завершить день".
DAY_START_CUTOFF_HOUR = 14


async def run_api_flow():
    username = settings.WPLAN_LOGIN
    password = settings.WPLAN_PASS
    is_start = datetime.now().hour < DAY_START_CUTOFF_HOUR

    async with WplanApiClient() as client:
        user = await client.login(username, password)
        logger.info(f'Logged in as {user["fio"]}')

        today = date.today().isoformat()
        absences = await client.get_absences()
        on_absence = any(a['startDate'] <= today <= a['endDate'] for a in absences)
        if on_absence:
            logger.info(f'{today} falls within an absence period - skipping start_end_workday')
            return

        result = await client.start_end_workday(is_start=is_start)
        logger.info(f'start_end_workday(is_start={is_start}) -> {result}')


def main():
    # current_url = 'https://wplan.office.lan'
    # with BrowserManager(debug=1) as browser:
    #     logger.info(f'Opening {current_url}')
    #     browser.open(current_url)
    #     for action in actions:
    #         logger.info(f'Executing {action.__name__}')
    #         browser.execute_action(action)
    #         logger.info(f'Finished {action.__name__}')
    # logger.info('Done')

    asyncio.run(run_api_flow())


if __name__ == "__main__":
    main()
