
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class SeleniumDriver:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None

    def get_driver(self):
        if self.driver is not None:
            return self.driver

        chrome_options = Options()

        if self.headless:
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

    def open(self, url: str):
        if self.driver is None:
            self.get_driver()
        self.driver.get(url)


    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        self.get_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
