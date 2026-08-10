"""Регрессионные тесты на находки аудита безопасности.

Каждый тест закрепляет одну исправленную уязвимость, чтобы её нельзя было
случайно вернуть при рефакторинге. Идентификаторы (H-1, H-3, ...)
соответствуют отчёту wplan-security-review.md.
"""

import asyncio
import io
import logging
import ssl
import tokenize
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pytest

from conftest import FAKE_TOKEN
from src import notify, settings
from src.api.wplan_client import WplanApiClient, _build_ssl_context, _ca_bundle_path


def executable_code(path: Path) -> str:
    """Исходник без комментариев и строковых литералов.

    Нужно для статических проверок: искать запрещённые конструкции в сыром
    тексте нельзя — они упоминаются в комментариях и docstring'ах, которые как
    раз объясняют, почему так делать не надо.
    """
    source = path.read_text(encoding="utf-8")
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        kept.append(tok.string)
    return " ".join(kept)


# --------------------------------------------------------------------------
# H-1: проверка TLS-сертификата включена и закреплён корпоративный корень
# --------------------------------------------------------------------------

def test_h1_ca_bundle_exists():
    assert _ca_bundle_path().exists(), (
        "Нет src/api/wplan-ca.pem — без него бинарь не проверит сертификат wplan"
    )


def test_h1_ssl_verification_is_enabled():
    ctx = _build_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED, "проверка цепочки должна быть обязательной"
    assert ctx.check_hostname is True, (
        "сверка имени хоста должна быть включена: у листового сертификата "
        "есть корректный SAN DNS:wplan.office.lan"
    )
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_h1_pinned_anchors_are_the_corporate_ca():
    ctx = _build_ssl_context()
    subjects = {
        dict(part[0] for part in cert["subject"]).get("commonName")
        for cert in ctx.get_ca_certs()
    }
    assert "RCA-CA" in subjects, "не закреплён корпоративный корневой CA"
    assert "office-SUB-CA" in subjects, "не закреплён промежуточный CA"


def test_h1_pinned_anchors_not_expired():
    """Корень действует до 2039, промежуточный до 2034 — но проверим явно.

    Если этот тест упал, сертификаты пора снять заново:
      openssl s_client -showcerts -connect wplan.office.lan:443 </dev/null
    """
    now = datetime.now(timezone.utc)
    for cert in _build_ssl_context().get_ca_certs():
        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        cn = dict(part[0] for part in cert["subject"]).get("commonName")
        assert not_after > now, f"сертификат {cn} истёк {not_after:%d.%m.%Y}"


def test_h1_no_ssl_disabling_left_in_source():
    """Прямая защита от возврата ssl=False."""
    code = executable_code(_ca_bundle_path().with_name("wplan_client.py")).replace(" ", "")
    assert "ssl=False" not in code, "в коде снова отключена проверка TLS"
    assert "verify_mode=ssl.CERT_NONE" not in code
    assert "check_hostname=False" not in code


# --------------------------------------------------------------------------
# H-3: bot-токен не попадает в логи
# --------------------------------------------------------------------------

class _FakeResponse:
    """Ответ Telegram API с ошибкой — воспроизводит условия утечки.

    ВАЖНО: raise_for_status() здесь обязан вести себя как настоящий aiohttp и
    бросать ClientResponseError с URL внутри. Без этого тест бесполезен: он
    проходил бы и на уязвимом коде, потому что тот падал бы на AttributeError,
    а не на реальном исключении с токеном в тексте.
    """

    def __init__(self, status, url):
        from yarl import URL

        self.status = status
        self.url = URL(url)
        self.reason = "Unauthorized" if status == 401 else "Server Error"
        self._request_info = aiohttp.RequestInfo(self.url, "POST", {}, self.url)

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                self._request_info, (), status=self.status, message=self.reason
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, status=401, raise_exc=None, **kwargs):
        self._status = status
        self._raise_exc = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResponse(self._status, url)


def test_h3_token_is_actually_in_the_url():
    """Санити-чек: токен действительно часть URL, значит риск реален."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    assert FAKE_TOKEN in url


def test_h3_aiohttp_exception_would_leak_the_url():
    """Документируем корень проблемы: str(ClientResponseError) содержит URL.

    Именно поэтому в notify.py нельзя вызывать raise_for_status() и
    логировать исключение с трейсбеком.
    """
    from yarl import URL

    url = URL(f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage")
    info = aiohttp.RequestInfo(url, "POST", {}, url)
    exc = aiohttp.ClientResponseError(info, (), status=401, message="Unauthorized")
    assert FAKE_TOKEN in str(exc), "поведение aiohttp изменилось — пересмотреть notify.py"


@pytest.mark.parametrize(
    "session_kwargs",
    [
        {"status": 401},
        {"status": 500},
        {"raise_exc": aiohttp.ClientConnectorError(None, OSError("boom"))},
        {"raise_exc": asyncio.TimeoutError()},
        {"raise_exc": RuntimeError("неожиданная ошибка")},
    ],
)
def test_h3_token_never_reaches_the_log(monkeypatch, caplog, session_kwargs):
    """Главный тест H-3: ни при каком сбое токен не должен попасть в журнал."""
    monkeypatch.setattr(
        notify.aiohttp,
        "ClientSession",
        lambda **kw: _FakeSession(**session_kwargs),
    )

    with caplog.at_level(logging.DEBUG, logger=notify.logger.name):
        asyncio.run(notify.send_telegram_message("тестовое уведомление"))

    dump = "\n".join(
        f"{r.getMessage()} {r.exc_text or ''}" for r in caplog.records
    )
    assert FAKE_TOKEN not in dump, f"bot-токен утёк в лог:\n{dump}"
    assert "api.telegram.org/bot" not in dump, f"URL с токеном утёк в лог:\n{dump}"


def test_h3_notify_does_not_use_raise_for_status():
    """Статическая страховка: raise_for_status() в notify.py вернул бы утечку."""
    code = executable_code(Path(notify.__file__)).replace(" ", "")
    assert "raise_for_status" not in code
    assert "logger.exception" not in code
    assert "exc_info=True" not in code


def test_h3_failed_notification_does_not_raise():
    """Сбой уведомления не должен ронять основной прогон."""
    asyncio.run(notify.send_telegram_message("x"))  # реальной сети нет — не падаем


# --------------------------------------------------------------------------
# M-4: текст исключения не пересылается в Telegram дословно
# --------------------------------------------------------------------------

def uncommented_source(path: Path) -> str:
    """Исходник без строк-комментариев, но со строковыми литералами.

    Для проверок содержимого f-строк tokenize не подходит: в Python 3.11
    f-строка — один STRING-токен, а в 3.12 разбирается на части, и статическая
    проверка вела бы себя по-разному на разных версиях.
    """
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )


def test_m4_main_does_not_forward_raw_exception_text():
    import main

    source = uncommented_source(Path(main.__file__))
    assert "Ошибка wplan: {e}" not in source, (
        "сырой текст исключения снова уходит в Telegram: там оказываются "
        "внутренний хостнейм, полный URL эндпоинта и возможный трейсбек сервера"
    )
    assert "type(e).__name__" in source, "ожидаем пересылку только класса ошибки"


def test_m4_login_is_not_logged():
    import main

    source = uncommented_source(Path(main.__file__))
    assert "settings.WPLAN_LOGIN}" not in source, (
        "корпоративный логин снова пишется в журнал"
    )
    assert "WPLAN_LOGIN" in source, "логин по-прежнему должен использоваться для входа"


# --------------------------------------------------------------------------
# L-3: accessToken очищается при закрытии клиента
# --------------------------------------------------------------------------

def test_l3_close_clears_access_token():
    async def scenario():
        client = WplanApiClient()
        client._access_token = "секретный-jwt"
        await client.close()
        return client._access_token

    assert asyncio.run(scenario()) is None, "accessToken остался в атрибутах объекта"


# --------------------------------------------------------------------------
# L-5: понятная ошибка вместо голого KeyError
# --------------------------------------------------------------------------

def test_l5_missing_env_var_gives_readable_error(monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(settings.ConfigError) as excinfo:
        settings._require("TELEGRAM_CHAT_ID")
    message = str(excinfo.value)
    assert "TELEGRAM_CHAT_ID" in message
    assert ".env" in message or "wplan.env" in message


def test_l5_empty_env_var_is_rejected(monkeypatch):
    monkeypatch.setenv("WPLAN_PASS", "")
    with pytest.raises(settings.ConfigError):
        settings._require("WPLAN_PASS")


# --------------------------------------------------------------------------
# Явные таймауты (страховка от подвисания oneshot-юнита)
# --------------------------------------------------------------------------

def test_explicit_timeouts_are_set():
    from src.api import wplan_client

    assert wplan_client.REQUEST_TIMEOUT.total is not None
    assert wplan_client.REQUEST_TIMEOUT.total <= 120
    assert notify.NOTIFY_TIMEOUT.total is not None
    assert notify.NOTIFY_TIMEOUT.total <= 30
