import queue
from logging import getLogger

from src.actions import wplan_actions
from src.driver.selen_drv import SeleniumDriver

import tkinter as tk
from tkinter import ttk
import sys
import os
from PIL import Image, ImageTk
import threading

logger = getLogger(__name__)


def get_resource_path(filename):
    """Получение пути к ресурсу в PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(__file__), filename)


def show_gui():
    try:
        root = tk.Tk()
        root.title("wplan")
        root.geometry("300x250")
        root.resizable(False, False)

        # Заголовок
        ttk.Label(root, text="✅ wplan запущен",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Пробуем загрузить гифку
        try:
            gif_path = get_resource_path("wplan.gif")
            img = Image.open(gif_path)

            # Конвертируем для tkinter
            tk_image = ImageTk.PhotoImage(img)
            img_label = ttk.Label(root, image=tk_image)
            img_label.image = tk_image  # важно сохранить ссылку!
            img_label.pack(pady=10)

        except Exception as e:
            # Запасной вариант
            ttk.Label(root, text="🎬 Выполняется...",
                      font=("Arial", 12)).pack(pady=20)

        # Прогресс-бар
        progress = ttk.Progressbar(root, mode='indeterminate', length=250)
        progress.pack(pady=15)
        progress.start(15)

        # Автозакрытие
        def close():
            root.destroy()

        root.after(3500, close)
        root.mainloop()

    except Exception:
        pass  # Если GUI не работает, просто игнорируем



def run_app(actions: tuple, url: str):
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


def main(actions: tuple, url: str):
    work_queue = queue.Queue()

    def worker():
        try:
            run_app(actions, url)
            work_queue.put("DONE")
        except Exception as e:
            work_queue.put(f"ERROR: {e}")

    work_thread = threading.Thread(target=worker, daemon=True)
    work_thread.start()

    show_gui()

    # Проверяем результат работы
    try:
        result = work_queue.get(timeout=0.1)
        print(f"Результат: {result}")
    except queue.Empty:
        print("Основной код еще выполняется...")


if __name__ == "__main__":
    current_actions = (wplan_actions.login, wplan_actions.start_stop_day)
    current_url = "https://wplan.office.lan/"
    main(current_actions, current_url)
