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
    # systemd LoadCredentialEncrypted= расшифровывает секрет в tmpfs-файл
    # под CREDENTIALS_DIRECTORY перед запуском - используем его, если есть.
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


def _optional(env_var: str) -> str | None:
    """Как _require, но без исключения - для переменных, которых пока может
    не быть (например *_QUERY_TEXT до того, как текст запроса будет снят
    вручную с прода - см. self-heal в wplan_client.py)."""
    return os.environ.get(env_var) or None


# Полный текст persisted-query запроса (поле "query" в GraphQL-запросе).
# В обычном режиме Apollo Client отправляет только sha256-хэш запроса -
# сервер знает текст заранее и достаёт его из своего кэша. Текст нужен
# ТОЛЬКО для self-heal в wplan_client.py: если хэш вдруг протух
# (PERSISTED_QUERY_NOT_FOUND), клиент один раз повторяет запрос уже с этим
# полным текстом, и сервер сам переобновляет свой кэш для этого хэша.
# Пока текст для конкретной операции не задан - self-heal для неё просто
# недоступен, ошибка устаревшего хэша всплывает как раньше (см.
# QUERY_TEXT_ENV_VAR_BY_OPERATION и WplanApiError.__str__).
LOGIN_QUERY_TEXT = _optional("LOGIN_QUERY_TEXT")
VACATIONS_QUERY_TEXT = _optional("VACATIONS_QUERY_TEXT")
START_FINISH_QUERY_TEXT = _optional("START_FINISH_QUERY_TEXT")
ABSENCES_QUERY_TEXT = _optional("ABSENCES_QUERY_TEXT")

TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _require("TELEGRAM_CHAT_ID")

# Сравнивается с datetime.now().hour ПО ВРЕМЕНИ СЕРВЕРА (обычно UTC).
# Офис — Europe/Moscow (UTC+3), поэтому 11 здесь соответствует ~14:00 MSK.
DAY_START_CUTOFF_HOUR = 11