import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), override=True)


def _read_credential(name: str, env_var: str) -> str:
    # systemd's LoadCredentialEncrypted= decrypts into a tmpfs file under
    # $CREDENTIALS_DIRECTORY right before the service starts - prefer that over
    # a plaintext env var when running under such a unit.
    creds_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if creds_dir:
        cred_path = Path(creds_dir) / name
        if cred_path.exists():
            return cred_path.read_text().strip()
    return os.environ[env_var]


WPLAN_LOGIN = os.environ["WPLAN_LOGIN"]
WPLAN_PASS = _read_credential("wplan_pass", "WPLAN_PASS")

LOGIN_QUERY_HASH = os.environ["LOGIN_QUERY_HASH"]
VACATIONS_QUERY_HASH = os.environ["VACATIONS_QUERY_HASH"]
START_FINISH_QUERY_HASH = os.environ["START_FINISH_QUERY_HASH"]
ABSENCES_QUERY_HASH = os.environ["ABSENCES_QUERY_HASH"]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Между утренним (~10:00) и вечерним (~18:00) запуском ПО МЕСТНОМУ ВРЕМЕНИ
# ОФИСА (Europe/Moscow, UTC+3) - используется как граница, чтобы отличить
# "начать день" от "завершить день". datetime.now() берёт локальное время
# СЕРВЕРА (обычно UTC на VPS), поэтому это не 14, а 14-3=11 - если сервер
# не в UTC, пересчитайте под его локальный часовой пояс.
DAY_START_CUTOFF_HOUR = 11