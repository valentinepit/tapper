import json
import logging
import ssl
import sys
from pathlib import Path
from types import TracebackType
from typing import Any

import aiohttp

from src import settings

logger = logging.getLogger(__name__)

GRAPHQL_PATH = "/ru-RU/api/graphql"
CA_BUNDLE_NAME = "wplan-ca.pem"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10)
PERSISTED_QUERY_NOT_FOUND_CODE = "PERSISTED_QUERY_NOT_FOUND"


# operationName графql-запроса -> переменная окружения с его persisted-query
# хэшем. Нужно, чтобы при PERSISTED_QUERY_NOT_FOUND в логе/Telegram сразу было
# видно, какой из четырёх хэшей протух, а не просто "запрос не найден".
HASH_ENV_VAR_BY_OPERATION = {
    "Login": "LOGIN_QUERY_HASH",
    "PersonalVacationsByWorkingDays": "VACATIONS_QUERY_HASH",
    "StartOrFinishDay": "START_FINISH_QUERY_HASH",
    "AbsenceRequestAllPersonal": "ABSENCES_QUERY_HASH",
}

# operationName -> переменная окружения с ПОЛНЫМ ТЕКСТОМ запроса (см.
# settings.*_QUERY_TEXT). Используется только именами - за самим значением
# всегда лезем в settings заново на каждый вызов (см. _query_text_for), чтобы
# тесты могли подменять settings.XXX_QUERY_TEXT через monkeypatch.
QUERY_TEXT_ENV_VAR_BY_OPERATION = {
    "Login": "LOGIN_QUERY_TEXT",
    "PersonalVacationsByWorkingDays": "VACATIONS_QUERY_TEXT",
    "StartOrFinishDay": "START_FINISH_QUERY_TEXT",
    "AbsenceRequestAllPersonal": "ABSENCES_QUERY_TEXT",
}


def _query_text_for(operation_name: str) -> str | None:
    return {
        "Login": settings.LOGIN_QUERY_TEXT,
        "PersonalVacationsByWorkingDays": settings.VACATIONS_QUERY_TEXT,
        "StartOrFinishDay": settings.START_FINISH_QUERY_TEXT,
        "AbsenceRequestAllPersonal": settings.ABSENCES_QUERY_TEXT,
    }.get(operation_name)


class WplanApiError(Exception):
    def __init__(
        self,
        errors: list[dict[str, Any]] | None = None,
        operation_name: str | None = None,
    ):
        super().__init__(errors or [])
        self.errors: list[dict[str, Any]] = errors or []
        self.operation_name: str | None = operation_name

    def __str__(self) -> str:
        codes = [err.get("message", "?") for err in self.errors]
        summary = ", ".join(codes) or "неизвестная ошибка API"
        if not self.operation_name:
            return summary
        is_stale_hash = any(
            err.get("extensions", {}).get("code") == PERSISTED_QUERY_NOT_FOUND_CODE
            for err in self.errors
        )
        if is_stale_hash:
            env_var = HASH_ENV_VAR_BY_OPERATION.get(self.operation_name, "?")
            return (
                f"{summary} на этапе '{self.operation_name}' - "
                f"устарел persisted-query хэш, обновите {env_var}"
            )
        return f"{summary} (этап '{self.operation_name}')"


def _ca_bundle_path() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "src" / "api" / CA_BUNDLE_NAME
    return Path(__file__).with_name(CA_BUNDLE_NAME)


def _build_ssl_context() -> ssl.SSLContext:
    ca_path = _ca_bundle_path()
    if not ca_path.exists():
        raise RuntimeError(
            f"Не найден файл доверенных сертификатов {ca_path}. "
            "Снять его заново (с поднятым VPN):\n"
            "  openssl s_client -showcerts -connect wplan.office.lan:443 </dev/null "
            "2>/dev/null | awk '/BEGIN CERT/,/END CERT/'"
        )
    ctx = ssl.create_default_context(cafile=str(ca_path))
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class WplanApiClient:
    def __init__(self, base_url: str = "https://wplan.office.lan"):
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None

    async def __aenter__(self) -> "WplanApiClient":
        connector = aiohttp.TCPConnector(ssl=_build_ssl_context())
        self._session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(),
            connector=connector,
            timeout=REQUEST_TIMEOUT,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        self._access_token = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("WplanApiClient нужно использовать как 'async with'")
        return self._session

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._access_token:
            headers["authorization"] = f"Bearer {self._access_token}"
        return headers

    @staticmethod
    def _extensions(sha256_hash: str) -> dict[str, Any]:
        return {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}}

    def _unwrap(self, payload: dict[str, Any], operation_name: str) -> dict[str, Any]:
        if payload.get("errors"):
            raise WplanApiError(payload["errors"], operation_name=operation_name)
        return payload["data"]

    @staticmethod
    def _is_persisted_query_not_found(payload: dict[str, Any]) -> bool:
        return any(
            err.get("extensions", {}).get("code") == PERSISTED_QUERY_NOT_FOUND_CODE
            for err in payload.get("errors") or []
        )

    async def _send(
        self,
        method: str,
        operation_name: str,
        variables: dict[str, Any],
        sha256_hash: str,
        query_text: str | None,
    ) -> dict[str, Any]:
        extensions = self._extensions(sha256_hash)
        session = self._require_session()
        if method == "get":
            params: dict[str, Any] = {
                "operationName": operation_name,
                "variables": json.dumps(variables),
                "extensions": json.dumps(extensions),
            }
            if query_text:
                params["query"] = query_text
            async with session.get(
                f"{self.base_url}{GRAPHQL_PATH}", params=params, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

        body: dict[str, Any] = {
            "operationName": operation_name,
            "variables": variables,
            "extensions": extensions,
        }
        if query_text:
            body["query"] = query_text
        async with session.post(
            f"{self.base_url}{GRAPHQL_PATH}", json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _graphql(
        self,
        method: str,
        operation_name: str,
        variables: dict[str, Any],
        sha256_hash: str,
    ) -> dict[str, Any]:
        """Оптимистичный APQ-запрос (только хэш) + self-heal при протухшем хэше.

        Apollo Client в обычном режиме шлёт только sha256-хэш запроса - сервер
        достаёт текст из своего кэша по хэшу. Когда кэш вытесняется (TTL,
        рестарт бэкенда) или сам запрос правда сломан релизом wplan, сервер
        возвращает PERSISTED_QUERY_NOT_FOUND. В первом случае достаточно
        одного повторного запроса с полем query (полный текст) - APQ-протокол
        сам переобновит серверный кэш для этого хэша, и все следующие вызовы
        снова пойдут коротким путём (только хэш), пока кэш не протухнет заново.

        Различаем два исхода в логах маркером SELF_HEAL_OUTCOME=..., чтобы
        через пару недель по journalctl посчитать, что чаще: healed (реально
        протухший хэш) или breaking_change (сервер не принял и полный текст -
        значит, дело не в TTL, а в изменившейся схеме/контракте API wplan).
        """
        payload = await self._send(method, operation_name, variables, sha256_hash, query_text=None)
        if not self._is_persisted_query_not_found(payload):
            return self._unwrap(payload, operation_name)

        query_text = _query_text_for(operation_name)
        if not query_text:
            env_var = QUERY_TEXT_ENV_VAR_BY_OPERATION.get(operation_name, "?")
            logger.warning(
                "SELF_HEAL_OUTCOME=unavailable операция='%s' - хэш протух "
                "(PERSISTED_QUERY_NOT_FOUND), но текст запроса не снят с прода "
                "(%s не задан) - падаем как раньше, без повторной попытки",
                operation_name,
                env_var,
            )
            return self._unwrap(payload, operation_name)

        logger.info(
            "операция='%s': хэш протух (PERSISTED_QUERY_NOT_FOUND) - повторяю "
            "запрос с полным текстом query (APQ self-heal)",
            operation_name,
        )
        retry_payload = await self._send(
            method, operation_name, variables, sha256_hash, query_text=query_text
        )
        if self._is_persisted_query_not_found(retry_payload):
            logger.error(
                "SELF_HEAL_OUTCOME=breaking_change операция='%s' - сервер не "
                "принял даже полный текст запроса. Похоже не на протухший TTL "
                "хэша, а на реальный breaking change в API wplan - нужно "
                "смотреть руками, self-heal тут не поможет",
                operation_name,
            )
            return self._unwrap(retry_payload, operation_name)

        if retry_payload.get("errors"):
            # Хэш ожил (PERSISTED_QUERY_NOT_FOUND больше нет), но у самого
            # запроса другая ошибка - это не наш случай, пробрасываем как
            # обычную ошибку API без маркера self-heal.
            return self._unwrap(retry_payload, operation_name)

        logger.info(
            "SELF_HEAL_OUTCOME=healed операция='%s' - хэш протух, сам "
            "починился (сервер принял полный текст и обновил свой кэш "
            "persisted-query для этого хэша)",
            operation_name,
        )
        return self._unwrap(retry_payload, operation_name)

    async def _graphql_get(
        self, operation_name: str, variables: dict[str, Any], sha256_hash: str
    ) -> dict[str, Any]:
        return await self._graphql("get", operation_name, variables, sha256_hash)

    async def _graphql_post(
        self, operation_name: str, variables: dict[str, Any], sha256_hash: str
    ) -> dict[str, Any]:
        return await self._graphql("post", operation_name, variables, sha256_hash)

    async def login(self, username: str, password: str) -> dict[str, Any]:
        # Без захода на страницу входа Login отвечает INVALID_USER_OR_PASSWORD
        # даже с верными кредами - серверу нужна cookie-сессия со страницы.
        async with self._require_session().get(f"{self.base_url}/ru-RU/sign-in") as resp:
            resp.raise_for_status()

        variables = {
            "username": username,
            "password": password,
            "accessToken2Fa": "",
            "twoFactorCode": "",
            "code": "",
            "redirectUri": "",
            "source": 1,
        }
        data = await self._graphql_post("Login", variables, settings.LOGIN_QUERY_HASH)
        user = data["jwtLogin"]
        self._access_token = user["accessToken"]
        return user

    async def check_vacations(self) -> list[dict[str, Any]]:
        data = await self._graphql_get(
            "PersonalVacationsByWorkingDays", {}, settings.VACATIONS_QUERY_HASH
        )
        return data["personalVacationsByWorkingDays"]

    async def start_end_workday(self, is_start: bool) -> dict[str, Any]:
        return await self._graphql_post(
            "StartOrFinishDay", {"isStart": is_start}, settings.START_FINISH_QUERY_HASH
        )

    async def get_absences(self) -> list[dict[str, Any]]:
        data = await self._graphql_get(
            "AbsenceRequestAllPersonal", {}, settings.ABSENCES_QUERY_HASH
        )
        return data["absenceRequestAllPersonal"]
