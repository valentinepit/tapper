"""Регрессионные тесты на self-heal протухшего persisted-query хэша.

Идея: Apollo Client в норме шлёт только sha256-хэш запроса. Когда серверный
кэш вытесняет этот хэш (TTL/рестарт бэкенда wplan), сервер отвечает
PERSISTED_QUERY_NOT_FOUND. Раньше это сразу превращалось в WplanApiError и
падение всего прогона с подсказкой "обновите ХЭШ_ENV_VAR". Теперь, если у нас
сохранён полный текст запроса (settings.*_QUERY_TEXT), клиент один раз
повторяет запрос уже с этим текстом - по протоколу APQ сервер сам
переобновляет свой кэш, и запрос проходит без участия человека.

Тесты бьют по трём исходам, каждый со своим маркером в логе
(SELF_HEAL_OUTCOME=...), чтобы по journalctl можно было посчитать,
что реально происходит на проде:
  - healed       - хэш был протухший, self-heal его оживил;
  - breaking_change - сервер не принял и полный текст, значит дело не в
    TTL, а в настоящем изменении контракта API wplan;
  - unavailable  - текст запроса для этой операции ещё не снят с прода,
    поэтому повторной попытки вообще не было (старое поведение).
"""

import asyncio
import logging

import pytest
from conftest import FAKE_TOKEN  # noqa: F401 - гарантирует ту же загрузку conftest, что и другие тесты

from src import settings
from src.api import wplan_client
from src.api.wplan_client import WplanApiClient, WplanApiError

PERSISTED_QUERY_NOT_FOUND_ERRORS = [
    {"message": "PersistedQueryNotFound", "extensions": {"code": "PERSISTED_QUERY_NOT_FOUND"}}
]


class _FakeGraphQLResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeGraphQLSession:
    """Возвращает заготовленные ответы по очереди и запоминает, что было отправлено.

    Использует тот же контракт вызова, что и настоящий aiohttp.ClientSession
    (.get/.post с именованными kwargs params/json/headers) - именно эти kwargs
    и проверяются в тестах, чтобы убедиться, что "query" реально уходит в
    повторном запросе и не уходит в первом (оптимистичном).
    """

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls: list[tuple[str, dict]] = []

    def _next(self, method, **kwargs):
        self.calls.append((method, kwargs))
        return _FakeGraphQLResponse(self._payloads.pop(0))

    def get(self, url, **kwargs):
        return self._next("get", url=url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("post", url=url, **kwargs)


def _client_with_fake_session(fake_session) -> WplanApiClient:
    client = WplanApiClient()
    client._session = fake_session  # минуем __aenter__ - реальный TLS/сокет тут не нужен
    return client


def test_self_heal_recovers_when_query_text_is_known(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ABSENCES_QUERY_TEXT", "query AbsenceRequestAllPersonal { id }")

    fake_session = _FakeGraphQLSession(
        [
            {"errors": PERSISTED_QUERY_NOT_FOUND_ERRORS},
            {"data": {"absenceRequestAllPersonal": []}},
        ]
    )
    client = _client_with_fake_session(fake_session)

    with caplog.at_level(logging.INFO, logger=wplan_client.logger.name):
        result = asyncio.run(client.get_absences())

    assert result == []
    assert len(fake_session.calls) == 2, "должно быть ровно две попытки: без текста и с текстом"

    _, first_kwargs = fake_session.calls[0]
    _, second_kwargs = fake_session.calls[1]
    assert "query" not in first_kwargs["params"], "первая попытка обязана быть оптимистичной (без текста)"
    assert second_kwargs["params"]["query"] == "query AbsenceRequestAllPersonal { id }"

    dump = "\n".join(r.getMessage() for r in caplog.records)
    assert "SELF_HEAL_OUTCOME=healed" in dump


def test_self_heal_reports_breaking_change_when_full_query_also_rejected(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ABSENCES_QUERY_TEXT", "query AbsenceRequestAllPersonal { id }")

    fake_session = _FakeGraphQLSession(
        [
            {"errors": PERSISTED_QUERY_NOT_FOUND_ERRORS},
            {"errors": PERSISTED_QUERY_NOT_FOUND_ERRORS},
        ]
    )
    client = _client_with_fake_session(fake_session)

    with caplog.at_level(logging.INFO, logger=wplan_client.logger.name):
        with pytest.raises(WplanApiError):
            asyncio.run(client.get_absences())

    assert len(fake_session.calls) == 2, "self-heal обязан попробовать полный текст ровно один раз"
    dump = "\n".join(r.getMessage() for r in caplog.records)
    assert "SELF_HEAL_OUTCOME=breaking_change" in dump


def test_self_heal_unavailable_without_captured_query_text(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ABSENCES_QUERY_TEXT", None)

    fake_session = _FakeGraphQLSession([{"errors": PERSISTED_QUERY_NOT_FOUND_ERRORS}])
    client = _client_with_fake_session(fake_session)

    with caplog.at_level(logging.INFO, logger=wplan_client.logger.name):
        with pytest.raises(WplanApiError):
            asyncio.run(client.get_absences())

    assert len(fake_session.calls) == 1, "без сохранённого текста повторной попытки быть не должно"
    dump = "\n".join(r.getMessage() for r in caplog.records)
    assert "SELF_HEAL_OUTCOME=unavailable" in dump


def test_self_heal_does_not_trigger_on_unrelated_errors(monkeypatch, caplog):
    """Другие ошибки API не должны путаться с протухшим хэшем и не должны
    провоцировать повторный запрос."""
    monkeypatch.setattr(settings, "ABSENCES_QUERY_TEXT", "query AbsenceRequestAllPersonal { id }")

    fake_session = _FakeGraphQLSession(
        [{"errors": [{"message": "SOME_OTHER_ERROR"}]}]
    )
    client = _client_with_fake_session(fake_session)

    with pytest.raises(WplanApiError):
        asyncio.run(client.get_absences())

    assert len(fake_session.calls) == 1, "нерелевантная ошибка не должна вызывать self-heal retry"


def test_self_heal_succeeds_transparently_for_a_mutation(monkeypatch):
    """StartOrFinishDay идёт через POST (мутация) - self-heal обязан работать
    и там, не только для GET-запросов чтения."""
    monkeypatch.setattr(settings, "START_FINISH_QUERY_TEXT", "mutation StartOrFinishDay { ok }")

    fake_session = _FakeGraphQLSession(
        [
            {"errors": PERSISTED_QUERY_NOT_FOUND_ERRORS},
            {"data": {"startOrFinishDay": {"ok": True}}},
        ]
    )
    client = _client_with_fake_session(fake_session)

    result = asyncio.run(
        client._graphql(
            "post",
            "StartOrFinishDay",
            {"isStart": True},
            settings.START_FINISH_QUERY_HASH,
        )
    )

    assert result == {"startOrFinishDay": {"ok": True}}
    assert len(fake_session.calls) == 2

    _, first_kwargs = fake_session.calls[0]
    _, second_kwargs = fake_session.calls[1]
    assert "query" not in first_kwargs["json"], "первая попытка обязана быть оптимистичной (без текста)"
    assert second_kwargs["json"]["query"] == "mutation StartOrFinishDay { ok }"
