import asyncio
import logging
import os
from datetime import date, datetime

# PyInstaller overrides LD_LIBRARY_PATH for its bundled libs, which breaks glibc's
# NSS "resolve" module (systemd-resolved integration) - DNS lookups fail inside the
# frozen binary even though the same hostname resolves fine via system tools.
# Restoring the pre-bootloader value (saved by PyInstaller as LD_LIBRARY_PATH_ORIG)
# before any network code runs is the documented workaround.
if 'LD_LIBRARY_PATH_ORIG' in os.environ:
    os.environ['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH_ORIG']
else:
    os.environ.pop('LD_LIBRARY_PATH', None)

if os.environ.get('WPLAN_DEBUG_DNS'):
    import socket
    print('LD_LIBRARY_PATH_ORIG:', repr(os.environ.get('LD_LIBRARY_PATH_ORIG')))
    print('LD_LIBRARY_PATH:', repr(os.environ.get('LD_LIBRARY_PATH')))
    for host in ('google.com', 'wplan.office.lan'):
        try:
            print(host, '->', socket.getaddrinfo(host, 443))
        except Exception as e:
            print(host, '-> ERROR', repr(e))
    raise SystemExit(0)

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
