import os
import sys
import tempfile


from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QMovie
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QProgressBar, QSplitter,
                             QTextEdit, QGroupBox)

from wplan.src.driver.selen_drv import BrowserManager
from wplan.src.actions import wplan_actions as actions


class SeleniumWorker(QThread):

    update_status = pyqtSignal(str)
    update_screenshot = pyqtSignal(str)
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

            # Запускаем браузер
            with BrowserManager(debug=True) as driver:
                driver.open("https://wplan.office.lan/")
                self.update_status.emit(f"🌐 Выполняю {len(self.actions_list)} действий...")

                # Выполняем все actions
                for i, action_func in enumerate(self.actions_list, 1):
                    if not self.running:
                        break

                    action_name = action_func.__name__
                    self.update_status.emit(f"[{i}/{len(self.actions_list)}] {action_name}...")

                    try:
                        # Выполняем action
                        success = driver.execute_action(action_func)

                        # Делаем скриншот после каждого действия
                        if hasattr(actions, 'take_screenshot'):
                            screenshot_path = actions.take_screenshot(driver)
                            self.update_screenshot.emit(screenshot_path)

                        self.action_completed.emit(action_name, success)

                    except Exception as e:
                        self.update_status.emit(f"❌ Ошибка в {action_name}: {str(e)}")
                        self.finished.emit(False, f"Ошибка в {action_name}: {str(e)}")
                        return

                self.update_status.emit("✅ Все действия выполнены успешно!")
                self.finished.emit(True, "Готово!")

        except Exception as e:
            self.update_status.emit(f"❌ Критическая ошибка: {str(e)}")
            self.finished.emit(False, f"Ошибка: {str(e)}")


    def stop(self):
        self.running = False
        if self.browser_manager:
            self.browser_manager.close()


class WplanApp(QWidget):

    def __init__(self):
        super().__init__()
        self.worker = None
        self.actions = [actions.login, actions.start_stop_day]
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("wplan - Автоматизация рабочего дня")
        self.setGeometry(100, 100, 1200, 700)

        # Главный layout
        main_layout = QHBoxLayout()

        splitter = QSplitter(Qt.Horizontal)

        # ЛЕВАЯ ПАНЕЛЬ: Гифка и статус
        left_panel = QWidget()
        left_layout = QVBoxLayout()

        # Гифка загрузки
        self.movie = QMovie()
        # Если есть гифка файл:
        # self.movie.setFileName("loading.gif")
        # self.movie.start()

        self.gif_label = QLabel()
        # self.gif_label.setMovie(self.movie)
        # Заглушка если нет гифки:
        self.gif_label.setText("🎬 wplan\nАвтоматизация")
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.gif_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                border: 2px dashed #3498db;
                border-radius: 10px;
                background-color: #f8f9fa;
            }
        """)
        self.gif_label.setMinimumHeight(200)
        left_layout.addWidget(self.gif_label)

        # Статус
        self.status_label = QLabel("Готов к запуску")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: #7f8c8d; padding: 10px;")
        left_layout.addWidget(self.status_label)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        left_layout.addWidget(self.progress_bar)

        # История действий
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setPlaceholderText("Здесь будет отображаться ход выполнения...")
        left_layout.addWidget(self.log_text)

        # Кнопки управления
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 Запустить")
        self.start_btn.clicked.connect(self.start_process)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #219653;
            }
        """)

        self.stop_btn = QPushButton("⏹️ Стоп")
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        left_layout.addLayout(button_layout)

        left_panel.setLayout(left_layout)

        # ПРАВАЯ ПАНЕЛЬ: Встроенный браузер Qt
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        browser_group = QGroupBox("Просмотр страницы (скриншоты)")
        browser_layout = QVBoxLayout()

        # QWebEngineView для отображения скриншотов через HTML
        self.web_view = QWebEngineView()
        self.web_view.setHtml("""
            <html>
                <body style="background-color: #ecf0f1; display: flex; justify-content: center; align-items: center; height: 100vh;">
                    <div style="text-align: center; color: #7f8c8d;">
                        <h2>🌐 wplan Браузер</h2>
                        <p>Здесь будут отображаться скриншоты выполнения</p>
                    </div>
                </body>
            </html>
        """)

        browser_layout.addWidget(self.web_view)
        browser_group.setLayout(browser_layout)
        right_layout.addWidget(browser_group)

        # Информация о текущем действии
        self.current_action_label = QLabel("Ожидание запуска...")
        self.current_action_label.setStyleSheet("padding: 10px; background-color: #f1f2f6;")
        right_layout.addWidget(self.current_action_label)

        right_panel.setLayout(right_layout)

        # Добавляем панели в сплиттер
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])  # Соотношение размеров

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Таймер для анимации прогресс-бара
        self.progress_value = 0
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.animate_progress)

    def animate_progress(self):
        """Анимация прогресс-бара"""
        self.progress_value = (self.progress_value + 1) % 100
        self.progress_bar.setValue(self.progress_value)

    def update_status(self, text):
        """Обновление статуса"""
        self.status_label.setText(text)
        self.log_text.append(f"• {text}")

        # Прокрутка вниз
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_screenshot(self, screenshot_path):
        """Обновление скриншота в браузере"""
        if os.path.exists(screenshot_path):
            # Отображаем скриншот через HTML
            html_content = f"""
            <html>
                <body style="margin: 0; padding: 20px; background-color: #2c3e50;">
                    <div style="text-align: center;">
                        <h3 style="color: white;">Скриншот выполнения</h3>
                        <img src="file://{screenshot_path}" style="max-width: 100%; border: 2px solid #3498db; border-radius: 5px;">
                        <p style="color: #bdc3c7;">Время: {os.path.basename(screenshot_path)}</p>
                    </div>
                </body>
            </html>
            """
            self.web_view.setHtml(html_content)

    def action_completed(self, action_name, success):
        """Обработка завершения action"""
        icon = "✅" if success else "❌"
        self.current_action_label.setText(f"{icon} {action_name} - {'Успешно' if success else 'Ошибка'}")

    def start_process(self):
        """Запуск процесса"""
        # Проверяем переменные окружения
        if not os.environ.get('WPLAN_LOGIN') or not os.environ.get('WPLAN_PASS'):
            self.update_status("❌ Ошибка: не установлены WPLAN_LOGIN или WPLAN_PASS")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # Запускаем анимацию
        self.progress_timer.start(50)
        self.update_status("🚀 Начинаю выполнение...")

        # Создаем и запускаем worker
        self.worker = SeleniumWorker(self.actions)
        self.worker.update_status.connect(self.update_status)
        self.worker.update_screenshot.connect(self.update_screenshot)
        self.worker.action_completed.connect(self.action_completed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_process(self):
        """Остановка процесса"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.update_status("⏹️ Остановка...")
            self.stop_btn.setEnabled(False)

    def on_finished(self, success, message):
        """Обработка завершения всего процесса"""
        self.progress_timer.stop()
        self.progress_bar.setValue(100 if success else 0)

        self.update_status(message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Обновляем гифку/текст
        if success:
            self.gif_label.setText("✅ Готово!\nВсе действия выполнены")
            self.gif_label.setStyleSheet("""
                QLabel {
                    font-size: 24px;
                    font-weight: bold;
                    color: #27ae60;
                    padding: 20px;
                    border: 2px solid #27ae60;
                    border-radius: 10px;
                    background-color: #d5f4e6;
                }
            """)
        else:
            self.gif_label.setText("❌ Ошибка!\nПроверьте логи")

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)  # Ждем 2 секунды

        # Удаляем временные файлы
        temp_dir = tempfile.gettempdir()
        for file in os.listdir(temp_dir):
            if file.startswith("wplan_screenshot"):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except:
                    pass

        event.accept()


def main():
    """Точка входа"""
    app = QApplication(sys.argv)

    # Проверяем переменные окружения
    if not os.environ.get('WPLAN_LOGIN') or not os.environ.get('WPLAN_PASS'):
        print("❌ Ошибка: установите переменные окружения:")
        print("   export WPLAN_LOGIN='ваш_логин'")
        print("   export WPLAN_PASS='ваш_пароль'")
        print("\nДобавьте эти строки в ~/.zshrc")

        # Простое окно с ошибкой
        error_window = QWidget()
        error_window.setWindowTitle("Ошибка")
        layout = QVBoxLayout()

        label = QLabel("❌ Установите переменные окружения:\n\n"
                       "export WPLAN_LOGIN='ваш_логин'\n"
                       "export WPLAN_PASS='ваш_пароль'\n\n"
                       "Добавьте в ~/.zshrc")
        label.setFont(QFont("Monospace", 11))

        layout.addWidget(label)
        error_window.setLayout(layout)
        error_window.show()

        return app.exec_()

    # Запускаем главное окно
    window = WplanApp()
    window.show()

    return app.exec_()


if __name__ == "__main__":
    main()