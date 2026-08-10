"""Фиктивное окружение для тестов.

src.settings читает os.environ на уровне модуля, поэтому переменные нужно
выставить ДО первого импорта — этот файл pytest подхватывает раньше тестов.
Значения намеренно нереальные.
"""

import os

_FAKE_ENV = {
    "WPLAN_LOGIN": "test_user@office.lan",
    "WPLAN_PASS": "test-password-not-real",
    "LOGIN_QUERY_HASH": "0" * 64,
    "VACATIONS_QUERY_HASH": "1" * 64,
    "START_FINISH_QUERY_HASH": "2" * 64,
    "ABSENCES_QUERY_HASH": "3" * 64,
    # Формат настоящего токена, но значение выдуманное. Именно эту строку
    # тесты ищут в логах, проверяя, что она никуда не утекает.
    "TELEGRAM_BOT_TOKEN": "123456789:AA_FAKE_TOKEN_FOR_TESTS_DO_NOT_USE_xyz",
    "TELEGRAM_CHAT_ID": "999999999",
}

# Строго ДО остальных переменных: иначе load_dotenv(override=True) в
# src/settings.py нашёл бы настоящий .env и подменил бы фиктивные значения
# реальными кредами.
os.environ["WPLAN_SKIP_DOTENV"] = "1"

for _key, _value in _FAKE_ENV.items():
    os.environ.setdefault(_key, _value)

FAKE_TOKEN = _FAKE_ENV["TELEGRAM_BOT_TOKEN"]
