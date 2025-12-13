import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class BrowserManager:
    def __init__(self, debug=False):
        self.debug = debug
        self.driver = None
        self.wait = None
        self.start_browser()

    def start_browser(self):
        """Запуск браузера"""
        options = Options()

        if not self.debug:
            options.add_argument("--headless")  # Фоновый режим
        else:
            options.add_argument("--start-maximized")
            options.add_argument("--window-size=1200,800")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

        # Обязательные опции для стабильности
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")

        print(f"🚀 Запускаю браузер (debug={self.debug})...")

        try:
            service = Service(ChromeDriverManager().install())

            self.driver = webdriver.Chrome(
                service=service,
                options=options
            )

            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.driver.implicitly_wait(15)
            self.wait = WebDriverWait(self.driver, 20)

            print("✅ Браузер успешно запущен!")

        except Exception as e:
            print(f"❌ Ошибка при запуске браузера: {e}")
            raise

    def open(self, url):
        if not self.driver:
            raise Exception("Браузер не инициализирован!")

        print(f"🌐 Открываю: {url}")
        self.driver.get(url)

        time.sleep(2)

        self.wait.until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        print(f"📄 Заголовок: {self.driver.title}")
        print(f"🔗 URL: {self.driver.current_url}")

        if self.debug:
            screenshot_path = f"/tmp/wplan_debug_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"📸 Скриншот сохранен: {screenshot_path}")

    def execute_action(self, action_func):

        if not self.driver:
            raise Exception("Браузер не инициализирован!")

        return action_func(self.driver)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.driver:
            print("🛑 Закрываю браузер...")
            try:
                self.driver.quit()
            except:
                pass
            finally:
                self.driver = None