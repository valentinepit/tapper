import os
import time

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QMovie
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QSplitter,
    QTextEdit, QApplication
)

from .styles import (
    label_style_2,
    current_action_style, descriptions,
    logs_style, progress_bar_style,
    status_style, header_style
)
from ..actions import wplan_actions as actions
from ..driver.selen_drv import BrowserManager


class SeleniumWorker(QThread):
    update_status = pyqtSignal(str)
    update_gif_state = pyqtSignal(str)
    action_completed = pyqtSignal(str, bool)
    finished = pyqtSignal(bool, str)

    def __init__(self, actions_list):
        super().__init__()
        self.actions_list = actions_list
        self.running = True

    def run(self):
        try:
            self.update_status.emit("🚀 Инициализация браузера...")
            self.update_gif_state.emit("browser")

            with BrowserManager(debug=False) as driver:
                driver.open("https://wplan.office.lan/")

                for i, action in enumerate(self.actions_list, 1):
                    if not self.running:
                        return

                    name = action.__name__
                    self.update_status.emit(f"▶ Выполняю: {name}")
                    self.update_gif_state.emit(f"action_{i}")

                    success = driver.execute_action(action)
                    self.action_completed.emit(name, success)
                    time.sleep(1)

            self.update_gif_state.emit("complete")
            self.finished.emit(True, "✅ Все действия выполнены")

        except Exception as e:
            self.update_gif_state.emit("error")
            self.finished.emit(False, str(e))

    def stop(self):
        self.running = False

class WplanApp(QWidget):

    def __init__(self, auto_start=False):
        self.auto_start = auto_start
        super().__init__()

        self.actions = [actions.login, actions.start_stop_day]
        self.worker = None
        self.movies = {}
        self.current_movie = None

        self.init_ui()
        self.load_gifs()

        QTimer.singleShot(800, self.start_process)

    # ---------------- UI ----------------
    def init_ui(self):
        self.setWindowTitle("wplan — автоматизация")
        self.setGeometry(100, 100, 1100, 650)

        main = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)

        # LEFT
        left = QWidget()
        left_l = QVBoxLayout()

        title = QLabel("🎯 wplan")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet(header_style)
        left_l.addWidget(title)

        self.status_label = QLabel("Ожидание запуска")
        self.status_label.setStyleSheet(status_style)
        self.status_label.setAlignment(Qt.AlignCenter)
        left_l.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setStyleSheet(progress_bar_style)
        left_l.addWidget(self.progress)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(logs_style)
        left_l.addWidget(self.log_text)

        left.setLayout(left_l)

        # RIGHT
        right = QWidget()
        right_l = QVBoxLayout()

        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.setStyleSheet(label_style_2)
        right_l.addWidget(self.gif_label)

        self.gif_description = QLabel("Готов к запуску")
        self.gif_description.setAlignment(Qt.AlignCenter)
        right_l.addWidget(self.gif_description)

        self.current_action = QLabel("💤")
        self.current_action.setAlignment(Qt.AlignCenter)
        self.current_action.setStyleSheet(current_action_style)
        right_l.addWidget(self.current_action)

        right.setLayout(right_l)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([400, 700])

        main.addWidget(splitter)
        self.setLayout(main)

    def load_gifs(self):
        base = os.path.join(os.path.dirname(__file__), "gifs")

        def load(name):
            path = os.path.join(base, f"{name}.gif")
            movie = QMovie(path)
            movie.setScaledSize(QSize(400, 400))
            return movie

        self.movies = {
            "browser": load("browser"),
            "action_1": load("login"),
            "action_2": load("push_the_button"),
            "complete": load("complete"),
            "error": load("error"),
        }

        self.set_movie("browser")

    def set_movie(self, key):
        if self.current_movie:
            self.current_movie.stop()

        self.current_movie = self.movies.get(key)
        if not self.current_movie:
            return

        self.gif_label.setMovie(self.current_movie)
        self.current_movie.start()

        self.gif_description.setText(descriptions.get(key, key))

    def update_gif_state(self, state):
        self.set_movie(state)

    def start_process(self):
        if not os.environ.get("WPLAN_LOGIN") or not os.environ.get("WPLAN_PASS"):
            self.update_status("❌ Нет переменных окружения")
            QTimer.singleShot(3000, QApplication.quit)
            return

        self.worker = SeleniumWorker(self.actions)
        self.worker.update_status.connect(self.update_status)
        self.worker.update_gif_state.connect(self.update_gif_state)
        self.worker.action_completed.connect(self.on_action)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def update_status(self, text):
        self.status_label.setText(text)
        self.log_text.append(text)

    def on_action(self, name, success):
        icon = "✅" if success else "❌"
        self.current_action.setText(f"{icon} {name}")

    def on_finished(self, success, message):
        self.update_status(message)
        QTimer.singleShot(2000, QApplication.quit)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()
