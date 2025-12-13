from logging import getLogger

from src.actions import wplan_actions
from src.driver.selen_drv import SeleniumDriver

logger = getLogger(__name__)


def main(actions: tuple, url: str):
    with SeleniumDriver() as browser:
        logger.info("Start process with url: %s", url)
        try:
            browser.open(url)
            for action in actions:
                action(browser.driver)
            logger.info(browser.driver.title)
            logger.info("Done")
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    current_actions = (wplan_actions.login, wplan_actions.start_stop_day)
    current_url = "https://wplan.office.lan/"
    main(current_actions, current_url)
