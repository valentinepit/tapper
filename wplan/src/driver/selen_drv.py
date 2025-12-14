import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class BrowserManager:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.driver = None

    def get_driver(self):
        if self.driver is not None:
            return self.driver

        chrome_options = Options()

        if not self.debug:
            chrome_options.add_argument("--headless=new")

        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-extensions")

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        return self.driver

    def open(self, url):
        if not self.driver:
            raise Exception("Браузер не инициализирован!")

        print(f"Открываю: {url}")
        self.driver.get(url)

        time.sleep(2)

        print(f"Заголовок: {self.driver.title}")
        print(f"URL: {self.driver.current_url}")

    def execute_action(self, action_func):

        if not self.driver:
            raise Exception("Браузер не инициализирован!")

        return action_func(self.driver)

    def __enter__(self):
        self.get_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.driver:
            print("Закрываю браузер...")
            try:
                self.driver.quit()
            except:
                pass
            finally:
                self.driver = None

    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
