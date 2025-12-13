start_button_style = """
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-size: 16px;
    }

    QPushButton:hover {
        background-color: #2980b9;
    }

    QPushButton:pressed {
        background-color: #2980b9;
    }
"""

push_button_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 15px;
                border-radius: 10px;
                border: 2px solid #c0392b;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #c0392b, stop:1 #a93226);
                border: 2px solid #922b21;
            }
            QPushButton:pressed {
                background: #922b21;
            }
            QPushButton:disabled {
                background: #95a5a6;
                border: 2px solid #7f8c8d;
            }
        """

group_box_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 3px solid #3498db;
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
            }
        """

label_style = """
            QLabel {
                background-color: #2c3e50;
                border-radius: 15px;
                border: 3px solid #34495e;
            }
        """

label_style_2 = """
            QLabel {
                color: white;
                background-color: #2c3e50;
                border-radius: 15px;
                border: 3px solid #34495e;
                font-weight: bold;
            }
        """

current_action_style = """
            QLabel {
                padding: 20px;
                background: #ecf0f1;
                border-radius: 10px;
                border-left: 6px solid #3498db;
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                margin-top: 10px;
            }
        """

speeds = {
            "start": 100,  # Нормальная скорость
            "browser_starting": 80,  # Чуть медленнее
            "browser_ready": 100,  # Нормальная
            "working": 60,  # Быстрая работа
            "login": 120,  # Медленно для важного действия
            "important_action": 70,  # Средняя скорость
            "success_blink": 30,  # Очень быстрое мигание
            "warning": 150,  # Медленно, внимание!
            "complete": 200,  # Очень медленно, завершение
            "error": 100,  # Нормальная с паузами
            "critical_error": 50,  # Быстро, тревога!
            "stopped": 1000  # Очень медленно, почти стоп
        }

descriptions = {
    "start": "Запуск системы...",
    "browser_starting": "Инициализация браузера...",
    "browser_ready": "Браузер готов! Открываю страницу...",
    "working": "Выполняю автоматизацию...",
    "login": "Авторизация в системе wplan...",
    "important_action": "Обработка рабочего дня...",
    "success_blink": "Действие успешно выполнено!",
    "warning": "Внимание: небольшие проблемы",
    "complete": "✅ Все действия завершены успешно!",
    "error": "❌ Ошибка выполнения",
    "critical_error": "🔥 Критическая ошибка!",
    "stopped": "⏹️ Выполнение остановлено"
}

success_blink_style = """
                QLabel {
                    background-color: #2c3e50;
                    border-radius: 15px;
                    border: 3px solid #e74c3c;
                }
            """

complite_style = """
                QLabel {
                    background-color: #2c3e50;
                    border-radius: 15px;
                    border: 3px solid #2ecc71;
                }
            """

# окошко с логами
logs_style = """
            QTextEdit {
                font-family: "Consolas", "Monospace";
                font-size: 11px;
                background-color: black;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                padding: 8px;
            }
        """

progress_bar_style = """
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                height: 30px;
                font-size: 14px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2ecc71);
                border-radius: 6px;
            }
        """

# кнопка "готов к запуску"
status_style = """
            QLabel {
                color: #2c3e50;
                padding: 12px;
                background-color: #f1f2f6;
                border: 2px solid #dfe4ea;
                border-radius: 8px;
                min-height: 20px;
            }
        """


header_style = """
            QLabel {
                color: white;
                padding: 20px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2c3e50);
                border-radius: 10px;
                margin-bottom: 15px;
            }
        """

loaded_gif_style = """
                QLabel {
                    font-size: 32px;
                    font-weight: bold;
                    color: #2c3e50;
                    padding: 40px;
                    border: 3px dashed #3498db;
                    border-radius: 15px;
                    background-color: #f8f9fa;
                }
            """