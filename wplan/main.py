import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from src.window.gif_window import WplanApp


def main():
    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    if not os.environ.get('WPLAN_LOGIN') or not os.environ.get('WPLAN_PASS'):
        print("❌ Ошибка: установите переменные окружения:")
        print("   export WPLAN_LOGIN='ваш_логин'")
        print("   export WPLAN_PASS='ваш_пароль'")
        print("\nДобавьте эти строки в ~/.zshrc")

        error_window = QWidget()
        error_window.setWindowTitle("wplan - Ошибка")
        error_window.setGeometry(300, 300, 500, 200)

        layout = QVBoxLayout()

        error_icon = QLabel("❌")
        error_icon.setAlignment(Qt.AlignCenter)
        error_icon.setFont(QFont("Arial", 48))

        label = QLabel("Установите переменные окружения:\n\n"
                       "export WPLAN_LOGIN='ваш_логин'\n"
                       "export WPLAN_PASS='ваш_пароль'\n\n"
                       "Добавьте в ~/.zshrc")
        label.setFont(QFont("Monospace", 11))
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)

        layout.addWidget(error_icon)
        layout.addWidget(label)
        error_window.setLayout(layout)
        error_window.show()

        return app.exec_()

    window = WplanApp(auto_start=True)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    main()
