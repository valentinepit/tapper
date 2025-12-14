import os
import time

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QMovie
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QProgressBar, QSplitter,
                             QTextEdit, QGroupBox)

from ..actions import wplan_actions as actions
from ..driver.selen_drv import BrowserManager
from .styles import start_button_style, push_button_style, group_box_style, label_style, label_style_2, \
    current_action_style, speeds, descriptions, success_blink_style, complite_style, logs_style, progress_bar_style, \
    status_style, header_style, loaded_gif_style


class SeleniumWorker(QThread):
    update_status = pyqtSignal(str)
    update_gif_state = pyqtSignal(str)
    action_completed = pyqtSignal(str, bool)
    finished = pyqtSignal(bool, str)

    def __init__(self, actions_list):
        super().__init__()
        self.actions_list = actions_list
        self.browser_manager = None
        self.running = True

    def run(self):
        try:
            self.update_status.emit("🚀 Инициализация браузера...")
            self.update_gif_state.emit("start")  # Запускаем гифку

            # Запускаем браузер
            with BrowserManager(debug=False) as driver:
                self.update_gif_state.emit("browser_starting")
                time.sleep(1)

                driver.open("https://wplan.office.lan/")
                self.update_gif_state.emit("browser_ready")
                time.sleep(1)

                self.update_status.emit(f"🌐 Выполняю {len(self.actions_list)} действий...")
                self.update_gif_state.emit("working")

                # Выполняем все actions
                for i, action_func in enumerate(self.actions_list, 1):
                    if not self.running:
                        break

                    action_name = action_func.__name__
                    self.update_status.emit(f"[{i}/{len(self.actions_list)}] {action_name}...")

                    # Изменяем скорость гифки в зависимости от действия
                    if "login" in action_name.lower():
                        self.update_gif_state.emit("login")
                    elif "start" in action_name.lower() or "stop" in action_name.lower():
                        self.update_gif_state.emit("important_action")

                    try:
                        success = driver.execute_action(action_func)
                        self.action_completed.emit(action_name, success)

                        if success:
                            self.update_gif_state.emit("success_blink")
                            time.sleep(0.5)
                            self.update_gif_state.emit("working")
                        else:
                            self.update_gif_state.emit("warning")

                        time.sleep(1)

                    except Exception as e:
                        self.update_gif_state.emit("error")
                        self.update_status.emit(f"❌ Ошибка в {action_name}: {str(e)}")
                        self.finished.emit(False, f"Ошибка в {action_name}: {str(e)}")
                        return

                self.update_gif_state.emit("complete")
                time.sleep(2)
                self.update_status.emit("✅ Все действия выполнены успешно!")
                self.finished.emit(True, "Готово!")

        except Exception as e:
            self.update_gif_state.emit("critical_error")
            self.update_status.emit(f"❌ Критическая ошибка: {str(e)}")
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def stop(self):
        self.running = False
        self.update_gif_state.emit("stopped")
        if self.browser_manager:
            self.browser_manager.close()


class WplanApp(QWidget):

    def __init__(self, auto_start=False):
        super().__init__()
        self.worker = None
        self.actions = [actions.login, actions.start_stop_day]
        self.movie = None
        self.auto_start = auto_start  # Флаг автозапуска
        self.init_ui()
        self.load_gif()

        if self.auto_start:
            QTimer.singleShot(1000, self.start_process)

    def load_gif(self):
        gif_path = "wplan.gif"

        possible_paths = [
            gif_path,
            os.path.join(os.path.dirname(__file__), gif_path),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), gif_path),
            "/tmp/wplan.gif"
        ]

        loaded = False
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    self.movie = QMovie(path)
                    self.movie.setScaledSize(QSize(400, 400))
                    self.gif_label.setMovie(self.movie)
                    print(f"✅ Гифка загружена: {path}")
                    loaded = True
                    break
                except Exception as e:
                    print(f"❌ Ошибка загрузки гифки {path}: {e}")

        if not loaded:
            print("⚠️ Гифка не найдена, использую эмодзи")
            self.gif_label.setText("🎬 wplan\nАвтоматизация")
            self.gif_label.setStyleSheet(loaded_gif_style)

    def init_ui(self):
        self.setWindowTitle("wplan - Автоматизация рабочего дня")
        self.setGeometry(100, 100, 1200, 700)

        main_layout = QHBoxLayout()

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout()

        # Заголовок
        title_label = QLabel("🎯 wplan - Автоматизация")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet(header_style)
        left_layout.addWidget(title_label)

        status_group = QGroupBox("📊 Статус выполнения")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Готов к запуску")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 11))
        self.status_label.setStyleSheet(status_style)
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(progress_bar_style)
        status_layout.addWidget(self.progress_bar)

        status_group.setLayout(status_layout)
        left_layout.addWidget(status_group)

        # Логи выполнения
        log_group = QGroupBox("📝 История действий")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet(logs_style)
        self.log_text.setPlaceholderText("Здесь будет отображаться ход выполнения...")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        left_layout.addWidget(log_group)

        # Кнопки управления
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 Запустить автоматизацию")
        self.start_btn.clicked.connect(self.start_process)
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet(start_button_style)

        self.stop_btn = QPushButton("⏹️ Остановить выполнение")
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setStyleSheet(push_button_style)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        left_layout.addLayout(button_layout)

        left_panel.setLayout(left_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout()

        gif_group = QGroupBox("🎬 Визуализация процесса")
        gif_group.setStyleSheet(group_box_style)
        gif_layout = QVBoxLayout()

        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.setMinimumSize(400, 400)
        self.gif_label.setStyleSheet(label_style)

        self.gif_label.setText("wplan.gif\n\nОжидание загрузки...")
        self.gif_label.setFont(QFont("Arial", 14))
        self.gif_label.setStyleSheet(label_style_2)

        gif_layout.addWidget(self.gif_label)

        self.gif_description = QLabel("Готов к работе. Нажмите 'Запустить'")
        self.gif_description.setAlignment(Qt.AlignCenter)
        self.gif_description.setFont(QFont("Arial", 12, QFont.Bold))
        self.gif_description.setStyleSheet("color: #2c3e50; padding: 15px;")
        gif_layout.addWidget(self.gif_description)

        self.current_action_label = QLabel("💤 Ожидание запуска")
        self.current_action_label.setAlignment(Qt.AlignCenter)
        self.current_action_label.setStyleSheet(current_action_style)
        gif_layout.addWidget(self.current_action_label)

        gif_group.setLayout(gif_layout)
        right_layout.addWidget(gif_group)

        info_group = QGroupBox("ℹ️ Информация")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "Автоматизация рабочего дня wplan\n\n"
            "1. Вход в систему\n"
            "2. Отметка начала/окончания дня\n"
            "3. Логирование процесса\n\n"
            "Статус отображается в реальном времени"
        )
        info_text.setAlignment(Qt.AlignLeft)
        info_text.setWordWrap(True)
        info_text.setStyleSheet("padding: 15px; color: #34495e;")
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)

        right_panel.setLayout(right_layout)

        # Добавляем панели в сплиттер
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Таймер для анимации прогресс-бара
        self.progress_value = 0
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.animate_progress)

    def animate_progress(self):
        self.progress_value = (self.progress_value + 1) % 100
        self.progress_bar.setValue(self.progress_value)

    def update_gif_state(self, state):
        if not self.movie:
            return

        speed = speeds.get(state, 100)
        self.movie.setSpeed(speed)

        # Запускаем/останавливаем гифку
        if state in ["stopped", "complete", "error", "critical_error"]:
            if self.movie.state() == QMovie.Running:
                self.movie.stop()
            # Для завершения показываем последний кадр
            if state == "complete":
                pixmap = self.movie.currentPixmap()
                if not pixmap.isNull():
                    self.gif_label.setPixmap(pixmap.scaled(
                        400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
        else:
            if self.movie.state() != QMovie.Running:
                self.movie.start()

        # Обновляем описание
        self.gif_description.setText(descriptions.get(state, "Выполнение..."))

        if state == "success_blink":
            QTimer.singleShot(500, lambda: self.update_gif_state("working"))
        elif state == "error":
            self.gif_label.setStyleSheet(success_blink_style)
        elif state == "complete":
            self.gif_label.setStyleSheet(complite_style)

    def update_status(self, text):
        self.status_label.setText(text)
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {text}")

        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def action_completed(self, action_name, success):
        icon = "✅" if success else "❌"
        color = "#27ae60" if success else "#e74c3c"
        self.current_action_label.setText(
            f'<span style="color: {color}; font-size: 16px;">{icon} {action_name}</span>'
        )

    def start_process(self):
        if not os.environ.get('WPLAN_LOGIN') or not os.environ.get('WPLAN_PASS'):
            self.update_status("❌ Ошибка: не установлены WPLAN_LOGIN или WPLAN_PASS")
            self.gif_description.setText("❌ Ошибка: проверьте переменные окружения")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)

        self.progress_timer.start(50)
        self.update_status("🚀 Начинаю выполнение...")
        self.update_gif_state("start")

        self.worker = SeleniumWorker(self.actions)
        self.worker.update_status.connect(self.update_status)
        self.worker.update_gif_state.connect(self.update_gif_state)
        self.worker.action_completed.connect(self.action_completed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_process(self):
        """Остановка процесса"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.update_status("⏹️ Остановка выполнения...")
            self.update_gif_state("stopped")
            self.stop_btn.setEnabled(False)
            self.progress_timer.stop()

    def on_finished(self, success, message):
        self.progress_timer.stop()
        self.progress_bar.setValue(100 if success else 0)

        self.update_status(message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self.update_gif_state("complete")
            self.gif_description.setText("🎉 Автоматизация завершена успешно!")

            QTimer.singleShot(3000, self.close_application)
        else:
            self.update_gif_state("error")
            self.gif_description.setText("❌ Произошла ошибка при выполнении")

            QTimer.singleShot(5000, self.close_application)

    def close_application(self):
        """Аккуратно закрываем приложение"""
        print("🛑 Автоматическое закрытие приложения...")

        # Добавляем сообщение в лог
        self.update_status("🛑 Завершение работы приложения...")

        # Если worker еще работает, останавливаем
        if self.worker and self.worker.isRunning():
            self.update_status("⏹️ Останавливаю выполнение...")
            self.worker.stop()
            self.worker.wait(1000)  # Ждем 1 секунду

        # Останавливаем гифку
        if self.movie:
            self.movie.stop()

        # Останавливаем таймер
        if self.progress_timer.isActive():
            self.progress_timer.stop()

        # Закрываем окно (это запустит closeEvent)
        self.close()

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        print("🛑 Обработка события закрытия окна...")

        # Если worker еще работает, останавливаем
        if self.worker and self.worker.isRunning():
            print("⏹️ Останавливаю worker...")
            self.worker.stop()
            self.worker.wait(1000)

        # Останавливаем гифку
        if self.movie:
            self.movie.stop()

        #  таймер
        if self.progress_timer.isActive():
            self.progress_timer.stop()

        event.accept()

        print("✅ Окно закрыто. Приложение завершится нормально.")