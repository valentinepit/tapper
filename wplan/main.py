from wplan.src.driver import BrowserManager
from src.actions import actions

import logging

logger = logging.getLogger(__name__)


def main():
    current_url = 'https://wplan.ru/login'
    with BrowserManager(debug=True) as browser:
        logger.info(f'Opening {current_url}')
        browser.open(current_url)
        for action in actions:
            logger.info(f'Executing {action.__name__}')
            browser.execute_action(action)
            logger.info(f'Finished {action.__name__}')
    logger.info('Done')


if __name__ == "__main__":
    main()
