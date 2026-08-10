import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

if os.environ.get("WPLAN_SKIP_DOTENV") != "1":
    load_dotenv(find_dotenv(), override=True)


class ConfigError(RuntimeError):
    """Не хватает обязательной переменной окружения."""


def _require(env_var: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        raise ConfigError(
            f"Не задана обязательная переменная окружения {env_var}. "
            "Локально: заполните .env по образцу .env.example. "
            "На сервере: проверьте /etc/wplan/wplan.env и права на него "
            "(должен быть читаем пользователем wplan)."
        )
    return value


def _read_credential(name: str, env_var: str) -> str:
    # systemd's LoadCredentialEncrypted= decrypts into a tmpfs file under
    # $CREDENTIALS_DIRECTORY right before the service starts - prefer that over
    # a plaintext env var when running under such a unit.
    creds_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if creds_dir:
        cred_path = Path(creds_dir) / name
        if cred_path.exists():
            secret = cred_path.read_text().strip()
            if secret:
                return secret
            raise ConfigError(
                f"Credential {name} расшифрован, но пуст: перезапишите "
                f"/etc/wplan/{name}.cred через systemd-creds encrypt."
            )
    return _require(env_var)


WPLAN_LOGIN = _require("WPLAN_LOGIN")
WPLAN_PASS = _read_credential("wplan_pass", "WPLAN_PASS")

LOGIN_QUERY_HASH = _require("LOGIN_QUERY_HASH")
VACATIONS_QUERY_HASH = _require("VACATIONS_QUERY_HASH")
START_FINISH_QUERY_HASH = _require("START_FINISH_QUERY_HASH")
ABSENCES_QUERY_HASH = _require("ABSENCES_QUERY_HASH")

TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _require("TELEGRAM_CHAT_ID")

# Между утренним (~10:00) и вечерним (~18:00) запуском ПО МЕСТНОМУ ВРЕМЕНИ
# ОФИСА (Europe/Moscow, UTC+3) - используется как граница, чтобы отличить
# "начать день" от "завершить день". datetime.now() берёт локальное время
# СЕРВЕРА (обычно UTC на VPS), поэтому это не 14, а 14-3=11 - если сервер
# не в UTC, пересчитайте под его локальный часовой пояс.
DAY_START_CUTOFF_HOUR = 11