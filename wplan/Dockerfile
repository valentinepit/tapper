# Сборка wplan-api в один исполняемый файл.
#
# Docker в текущей схеме деплоя НЕ обязателен: на VPS бинарь собирается
# напрямую через `poetry run pyinstaller wplan-api.spec` и запускается
# systemd-таймерами. Этот Dockerfile нужен только чтобы получить
# Linux-бинарь с macOS, не поднимая VPS-сборку.
#
# Предыдущая версия относилась к старой selenium-архитектуре: ставила
# selenium/pyqt5/pillow и указывала --hidden-import src.driver, src.actions -
# модули, которых в проекте больше нет, то есть собирала нерабочий артефакт.

FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        binutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости ставим из poetry.lock, а не свежайшие с PyPI: сборка должна быть
# воспроизводимой, иначе версии пакетов зависят от даты запуска docker build.
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir "poetry>=2.0,<3.0" && \
    poetry export --without-hashes --format requirements.txt --output requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Только то, что нужно для сборки (см. .dockerignore).
COPY main.py wplan-api.spec ./
COPY src ./src

RUN pyinstaller --clean --noconfirm wplan-api.spec

FROM debian:stable-slim

# Бинарь ходит в сеть и парсит недоверенный JSON - незачем делать это от root.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin --uid 10001 wplan

COPY --from=builder /app/dist/wplan-api /usr/local/bin/wplan-api

USER wplan
ENTRYPOINT ["/usr/local/bin/wplan-api"]
