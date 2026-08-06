import json

import aiohttp

from src import settings

GRAPHQL_PATH = "/ru-RU/api/graphql"


class WplanApiError(Exception):
    pass


class WplanApiClient:
    def __init__(self, base_url: str = "https://wplan.office.lan"):
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None

    async def __aenter__(self) -> "WplanApiClient":
        # wplan.office.lan использует внутренний self-signed сертификат, которому
        # не доверяет стандартный certifi-bundle aiohttp (хотя ОС/браузер его знают).
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(), connector=connector)
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _headers(self) -> dict:
        headers = {"content-type": "application/json"}
        if self._access_token:
            headers["authorization"] = f"Bearer {self._access_token}"
        return headers

    @staticmethod
    def _extensions(sha256_hash: str) -> dict:
        return {"persistedQuery": {"version": 1, "sha256Hash": sha256_hash}}

    def _unwrap(self, payload: dict) -> dict:
        if payload.get("errors"):
            raise WplanApiError(payload["errors"])
        return payload["data"]

    async def _graphql_get(self, operation_name: str, variables: dict, sha256_hash: str) -> dict:
        params = {
            "operationName": operation_name,
            "variables": json.dumps(variables),
            "extensions": json.dumps(self._extensions(sha256_hash)),
        }
        async with self._session.get(
            f"{self.base_url}{GRAPHQL_PATH}", params=params, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return self._unwrap(await resp.json())

    async def _graphql_post(self, operation_name: str, variables: dict, sha256_hash: str) -> dict:
        body = {
            "operationName": operation_name,
            "variables": variables,
            "extensions": self._extensions(sha256_hash),
        }
        async with self._session.post(
            f"{self.base_url}{GRAPHQL_PATH}", json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return self._unwrap(await resp.json())

    async def login(self, username: str, password: str) -> dict:
        # Как в браузере: заход на страницу входа заводит cookie-сессию
        # (NEXT_LOCALE и т.п.), без которой Login отвечает INVALID_USER_OR_PASSWORD
        # даже с верными кредами.
        async with self._session.get(f"{self.base_url}/ru-RU/sign-in") as resp:
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

    async def check_vacations(self) -> list:
        data = await self._graphql_get(
            "PersonalVacationsByWorkingDays", {}, settings.VACATIONS_QUERY_HASH
        )
        return data["personalVacationsByWorkingDays"]

    async def start_end_workday(self, is_start: bool) -> dict:
        return await self._graphql_post(
            "StartOrFinishDay", {"isStart": is_start}, settings.START_FINISH_QUERY_HASH
        )
