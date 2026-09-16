import json
import ssl
import sys
from pathlib import Path
from types import TracebackType
from typing import Any

import aiohttp

from src import settings

GRAPHQL_PATH = "/ru-RU/api/graphql"
CA_BUNDLE_NAME = "wplan-ca.pem"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10)


# operationName графql-запроса -> переменная окружения с его persisted-query
# хэшем. Нужно, чтобы при PERSISTED_QUERY_NOT_FOUND в логе/Telegram сразу было
# видно, какой из четырёх хэшей протух, а не просто "запрос не найден".
HASH_ENV_VAR_BY_OPERATION = {
    "Login": "LOGIN_QUERY_HASH",
    "PersonalVacationsByWorkingDays": "VACATIONS_QUERY_HASH",
    "StartOrFinishDay": "START_FINISH_QUERY_HASH",
    "AbsenceRequestAllPersonal": "ABSENCES_QUERY_HASH",
}


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
            err.get("extensions", {}).get("code") == "PERSISTED_QUERY_NOT_FOUND"
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

    async def _graphql_get(
        self, operation_name: str, variables: dict[str, Any], sha256_hash: str
    ) -> dict[str, Any]:
        params = {
            "operationName": operation_name,
            "variables": json.dumps(variables),
            "extensions": json.dumps(self._extensions(sha256_hash)),
        }
        async with self._require_session().get(
            f"{self.base_url}{GRAPHQL_PATH}", params=params, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return self._unwrap(await resp.json(), operation_name)

    async def _graphql_post(
        self, operation_name: str, variables: dict[str, Any], sha256_hash: str
    ) -> dict[str, Any]:
        body = {
            "operationName": operation_name,
            "variables": variables,
            "extensions": self._extensions(sha256_hash),
        }
        async with self._require_session().post(
            f"{self.base_url}{GRAPHQL_PATH}", json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return self._unwrap(await resp.json(), operation_name)

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
