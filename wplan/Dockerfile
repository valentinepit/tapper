FROM python:3.12-slim AS builder

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    binutils \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем весь проект
COPY . .

# Устанавливаем зависимости
RUN pip install --upgrade pip && \
    pip install selenium webdriver-manager pillow pyqt5 pyqtwebengine pyinstaller

# Собираем с указанием пути к src
RUN pyinstaller --onefile \
    --name wplan_linux \
    --add-data "src:src" \
    --hidden-import src.driver \
    --hidden-import src.actions \
    main.py

FROM debian:stable-slim
COPY --from=builder /app/dist/wplan_linux /wplan_linux
CMD ["/wplan_linux"]
