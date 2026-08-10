# WPLAN — автоматический старт/конец рабочего дня через API

Раньше это делалось через Selenium (эмуляция браузера). Сейчас `main.py` дёргает
GraphQL API `wplan.office.lan` напрямую (без браузера): логинится, смотрит,
не отпуск/day-off ли сегодня, и если рабочий день — жмёт кнопку начала или
конца дня (в зависимости от времени суток).

## Как это работает

`main.py` → `src/api/WplanApiClient`:
1. `login(username, password)` — GraphQL mutation `Login`.
2. `get_absences()` — GraphQL query `AbsenceRequestAllPersonal`, весь список отпусков/day-off'ов без фильтра.
3. Если сегодняшняя дата попадает в один из периодов из шага 2 — ничего не делаем (тихо, без уведомления).
4. Иначе `start_end_workday(is_start=...)` — GraphQL mutation `StartOrFinishDay`. `is_start` определяется по времени суток (`DAY_START_CUTOFF_HOUR` в `src/settings.py`, по умолчанию до 11:00 UTC / 14:00 MSK — начать день, после — завершить).

Ошибка сервера `EDITING_NOT_AVAILABLE` ("день уже был начат/завершён ранее") —
не баг, а штатная ситуация (кто-то/что-то уже переключил день); код логирует
её как INFO и завершается без ошибки (тоже без уведомления).

После реального успешного `start_end_workday` или любой другой (настоящей)
ошибки в Telegram приходит уведомление — см. "Настройка Telegram-уведомлений"
ниже. В уведомление об ошибке уходит только класс исключения или коды
GraphQL-ошибок, но не текст исключения целиком: в нём оказывались внутренний
хостнейм и полный URL эндпоинта, а Telegram — сторонний сервис. Подробности
всегда в журнале: `journalctl -u wplan`.

## TLS: проверка сертификата wplan

`wplan.office.lan` выписан внутренним AD CS, цепочка
`wplan.office.lan` → `office-SUB-CA` → `RCA-CA`. Этого корня нет в bundle
`certifi`, поэтому раньше в клиенте стояло `ssl=False` — а это отключало не
только проверку цепочки, но и сверку имени хоста, то есть любой на пути
трафика внутри сети мог перехватить логин, пароль и `accessToken`.

Сейчас клиент доверяет **только** корпоративному корню. Он лежит в
`src/api/wplan-ca.pem` — это публичные данные, сервер отдаёт их каждому
TLS-клиенту, секрета в файле нет. Закреплён именно корень (действует до 2039),
а не листовой сертификат `wplan.office.lan` (истекает 26.04.2027): иначе
пиннинг ломался бы при каждой ротации листа. Сверка имени хоста включена —
у листа есть корректный `SAN DNS:wplan.office.lan`.

Файл вкладывается внутрь собранного бинаря через `datas` в `wplan-api.spec`,
на рантайме читается из `sys._MEIPASS` (см. `_ca_bundle_path()`).

**Если появилась ошибка `CERTIFICATE_VERIFY_FAILED`** — скорее всего сменился
корневой CA. Снять цепочку заново (нужен доступ к wplan, то есть VPN):

```bash
openssl s_client -showcerts -connect wplan.office.lan:443 </dev/null 2>/dev/null \
  | awk '/BEGIN CERT/,/END CERT/'
```

В `src/api/wplan-ca.pem` оставить два **последних** блока цепочки —
промежуточный CA и корень, — затем пересобрать бинарь.

## Тесты

```bash
poetry install          # dev-группа с pytest ставится по умолчанию
poetry run pytest -q    # ожидается 20 passed
```

`tests/test_security_regressions.py` закрепляет исправления аудита
безопасности: включённую проверку TLS и состав закреплённых CA (в том числе
их срок действия), отсутствие утечки Telegram-токена в журнал, фильтрацию
текста исключений перед отправкой в Telegram, очистку `accessToken`,
внятные ошибки конфигурации. Тесты работают на фиктивном окружении из
`tests/conftest.py` и не ходят в сеть, поэтому запускаются без VPN.

Статический анализ:

```bash
poetry run bandit -r src main.py
poetry run pip-audit          # если установлен: проверка CVE в зависимостях
```

## Переменные окружения

| Переменная | Что это | Секрет? |
|---|---|---|
| `WPLAN_LOGIN` | логин (вида `login@office.lan`) | нет |
| `WPLAN_PASS` | пароль | **да** |
| `LOGIN_QUERY_HASH` | persisted-query хэш mutation `Login` | нет |
| `VACATIONS_QUERY_HASH` | хэш query `PersonalVacationsByWorkingDays` | нет |
| `START_FINISH_QUERY_HASH` | хэш mutation `StartOrFinishDay` | нет |
| `ABSENCES_QUERY_HASH` | хэш query `AbsenceRequestAllPersonal` | нет |
| `TELEGRAM_BOT_TOKEN` | токен личного бота-нотификатора (от @BotFather) | умеренно (доступ к боту, не к аккаунту) |
| `TELEGRAM_CHAT_ID` | ваш chat_id, куда бот шлёт сообщения | нет |
| `WPLAN_SKIP_DOTENV` | `1` отключает чтение `.env` (нужно только тестам) | нет |

Если обязательная переменная не задана, приложение падает на старте с
понятным `ConfigError`, а не с голым `KeyError` — но падает намеренно:
работать с пустым паролем хуже, чем не запуститься.

`TELEGRAM_BOT_TOKEN` подставляется в URL Bot API, поэтому в `src/notify.py`
нельзя вызывать `resp.raise_for_status()` и логировать исключения с
трейсбеком: строковое представление `aiohttp.ClientResponseError` содержит
URL целиком, и токен утёк бы в journald. За этим следит тест
`test_h3_token_never_reaches_the_log`.

Хэши — это Apollo persisted-query sha256 конкретного деплоя wplan (одинаковые
для всех сотрудников одной компании, не персональные секреты). Если у вас
другой инстанс wplan и хэши не совпадают — снимите свои через
DevTools → Network при логине/клике на сайте (см. `operationName`,
`extensions.persistedQuery.sha256Hash` в запросах к `/ru-RU/api/graphql`).

`wplan.office.lan` резолвится и открывается только из корпоративной сети —
для запуска откуда-либо ещё нужен VPN-туннель в эту сеть.

## Настройка Telegram-уведомлений

При успешном начале/окончании дня или при реальной ошибке бот присылает
сообщение в личку (тихие "штатные" случаи — отпуск, уже сделано кем-то — не
уведомляются, см. выше). Через Bot API (не через авторизацию как
пользователь) — проще и безопаснее для сервера без присмотра.

1. В Telegram написать **@BotFather** → `/newbot` → следовать подсказкам → получить токен (`TELEGRAM_BOT_TOKEN`).
2. Написать своему новому боту `/start` (боты не могут писать первыми — нужно самому начать диалог хотя бы раз).
3. Узнать свой `chat_id`:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   В ответе найти `"chat":{"id":...}` — это `TELEGRAM_CHAT_ID`.
4. Добавить обе переменные в `.env` (локально) и/или `/etc/wplan/wplan.env` (на VPS).

Проверить отдельно от основного флоу:
```bash
poetry run python -c "import asyncio; from src.notify import send_telegram_message; asyncio.run(send_telegram_message('test'))"
```

## Локальный запуск (разработка)

1. `poetry install`
2. Скопировать `.env.example` (в корне репозитория, на уровень выше `wplan/`) в `.env` и вписать свои `WPLAN_LOGIN`/`WPLAN_PASS` (хэши там уже настоящие, менять не нужно, если это тот же деплой wplan).
3. `poetry run pytest -q` — быстрая проверка, что окружение и код в порядке (VPN не требуется).
4. `poetry run python main.py`

Быть в корпоративной сети (или подключённым к её VPN) обязательно для шага 4 —
иначе `wplan.office.lan` не резолвится. Учтите, что шаг 4 выполняет реальное
действие: начинает или завершает ваш рабочий день в WPlan, в зависимости от
текущего часа и `DAY_START_CUTOFF_HOUR`.

## Продакшен: разворачивание на Linux VPS

Сценарий: VPS сам подключается к корпоративной сети через OpenVPN и дважды в
будний день (~10:00 и ~18:00, окно ±5 минут) без участия человека дёргает
`main.py`.

Готовые шаблоны systemd-юнитов — в `deploy/`.

### 0. Что нужно заранее

- SSH-доступ (root) к Ubuntu 22.04/24.04 VPS.
- Свой OpenVPN-клиентский конфиг от IT (`.ovpn`/сертификаты) для входа в корпоративную сеть.
- Свои `WPLAN_LOGIN`/`WPLAN_PASS`.

### 1. Системные пакеты

```bash
apt update
apt install -y git openvpn openvpn-systemd-resolved binutils
```

(`binutils` нужен `pyinstaller` на Linux, `openvpn-systemd-resolved` — чтобы VPN правильно прописывал DNS корпоративных доменов в `systemd-resolved`.)

### 2. OpenVPN-клиент

Положите свой конфиг от IT в `/etc/openvpn/client/<name>.conf` (`<name>` — любое имя, например `corp`).

Если конфиг требует логин/пароль (строка `auth-user-pass` без пути к файлу) —
без файла с кредами таймер зависнет на интерактивном запросе (нет TTY):

```bash
cat > /etc/openvpn/client/<name>.auth
# ввести логин, Enter, пароль, Enter, затем Ctrl+D
chown root:root /etc/openvpn/client/<name>.auth
chmod 600 /etc/openvpn/client/<name>.auth
sed -i 's|^auth-user-pass$|auth-user-pass /etc/openvpn/client/<name>.auth|' /etc/openvpn/client/<name>.conf
```

Если сеть использует split-DNS через `systemd-resolved` (домены вида `*.office.lan` резолвятся только через VPN) — допишите хуки:

```bash
echo 'script-security 2' >> /etc/openvpn/client/<name>.conf
echo 'up /etc/openvpn/update-systemd-resolved' >> /etc/openvpn/client/<name>.conf
echo 'down /etc/openvpn/update-systemd-resolved' >> /etc/openvpn/client/<name>.conf
echo 'down-pre' >> /etc/openvpn/client/<name>.conf
```

Поднимите и включите автозапуск:

```bash
systemctl enable --now openvpn-client@<name>
```

Автовосстановление при падении туннеля (важно — иначе один обрыв тихо
остановит всю автоматизацию до ручного вмешательства):

```bash
mkdir -p /etc/systemd/system/openvpn-client@<name>.service.d
cp deploy/openvpn-restart-override.conf /etc/systemd/system/openvpn-client@<name>.service.d/override.conf
systemctl daemon-reload
systemctl restart openvpn-client@<name>
```

Проверка резолвинга и доступности:

```bash
getent hosts wplan.office.lan
curl -k -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 5 https://wplan.office.lan/
```

`-k` здесь только потому, что корпоративного корня нет в системном хранилище
VPS — это проверка сетевой связности, а не сертификата. Само приложение
проверку **не** отключает: оно доверяет `src/api/wplan-ca.pem`. После шага 3
связку можно проверить уже строго, без `-k`:

```bash
curl --cacert /opt/wplan-src/wplan/src/api/wplan-ca.pem \
     -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 5 https://wplan.office.lan/
```

Если эта команда проходит, а `curl -k` тоже — значит пиннинг рабочий и бинарь
сможет подключиться.

### 3. Python / Poetry / код

```bash
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/valentinepit/tapper.git /opt/wplan-src
cd /opt/wplan-src && git checkout without-interface
cd wplan
~/.local/bin/poetry install
```

### 4. Тесты и сборка бинарника

Сначала тесты — они проверяют ровно те места, где легко всё сломать
(TLS-пиннинг, обращение с токеном, конфигурация):

```bash
~/.local/bin/poetry run pytest -q          # ожидается 20 passed
```

PyInstaller не кросс-компилирует — собирайте прямо на целевом сервере (не на macOS/Windows с последующим копированием):

```bash
~/.local/bin/poetry run pyinstaller --clean --noconfirm wplan-api.spec
```

Убедитесь, что корпоративный CA попал внутрь бинаря — без него запуск упадёт
с ошибкой «Не найден файл доверенных сертификатов»:

```bash
~/.local/bin/poetry run pyi-archive_viewer -l dist/wplan-api | grep -i pem
```

Ожидается строка, оканчивающаяся на `'src/api/wplan-ca.pem'`. Искать в бинаре
текст `BEGIN CERTIFICATE` бесполезно: `datas` лежат в сжатом CArchive, и
содержимое файлов в `strings` не появляется даже когда всё вложено правильно —
открытым текстом в TOC хранится только имя файла (`strings dist/wplan-api |
grep -c 'wplan-ca.pem'` вернёт `1`).

### 5. Системный пользователь

Приложению не нужен root: оно только ходит в сеть и распаковывает свой
PyInstaller-архив в приватный `/tmp`. Запуск от root означал бы, что любая
уязвимость в `aiohttp`, парсере JSON или bootloader'е компрометирует весь VPS,
а не один аккаунт wplan.

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin wplan
id wplan
```

### 6. Установка бинарника

```bash
mkdir -p /opt/wplan
install -o root -g root -m 0755 dist/wplan-api /opt/wplan/wplan-api
ls -l /opt/wplan/wplan-api
```

Владелец — `root`, пользователь `wplan` только читает и исполняет: так сервис
не сможет подменить собственный исполняемый файл.

### 7. Секреты

Несекретные значения (логин + 4 хэша + Telegram) — в `/etc/wplan/wplan.env`:

```bash
mkdir -p /etc/wplan
cat > /etc/wplan/wplan.env
```

Впишите (свои значения, `Ctrl+D` в конце; про `TELEGRAM_*` см. "Настройка Telegram-уведомлений" выше):

```
WPLAN_LOGIN=your_login@office.lan
LOGIN_QUERY_HASH=...
VACATIONS_QUERY_HASH=...
START_FINISH_QUERY_HASH=...
ABSENCES_QUERY_HASH=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

```bash
chown root:root /etc/wplan/wplan.env
chmod 600 /etc/wplan/wplan.env
chown root:root /etc/wplan && chmod 700 /etc/wplan
```

Пароль — отдельно, зашифрован через `systemd-creds` (не лежит на диске в
открытом виде; расшифровывается только самим systemd прямо перед запуском
сервиса, в tmpfs, не в файле):

```bash
systemd-creds encrypt --name=wplan_pass - /etc/wplan/wplan_pass.cred
# ввести пароль, затем Ctrl+D
chown root:root /etc/wplan/wplan_pass.cred
chmod 600 /etc/wplan/wplan_pass.cred
```

**Права на секреты остаются строгими `root:root 600` даже при `User=wplan`.**
И `EnvironmentFile=`, и `LoadCredentialEncrypted=` обрабатывает сам systemd от
root ещё до сброса привилегий: процесс получает готовые переменные окружения и
расшифрованный credential в tmpfs, а файлов не читает. Давать группе `wplan`
доступ к ним не нужно — проверить можно так (ожидается `Permission denied`,
и это правильный результат):

```bash
sudo -u wplan cat /etc/wplan/wplan.env
```

### 8. systemd-сервис и таймеры

```bash
cp deploy/wplan.service /etc/systemd/system/wplan.service
sed -i 's/YOUR_VPN_CONFIG_NAME/<name>/' /etc/systemd/system/wplan.service

# контроль: заглушка заменена, User=wplan на месте
grep -nE 'openvpn-client@|^User=|^Group=' /etc/systemd/system/wplan.service

cp deploy/wplan-morning.timer deploy/wplan-evening.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now wplan-morning.timer wplan-evening.timer
```

Юнит запускается от `wplan` и закрыт набором директив изоляции
(`ProtectSystem=strict`, `PrivateTmp`, `NoNewPrivileges`, пустой
`CapabilityBoundingSet`, `SystemCallFilter=@system-service` и прочие).
Оценить результат:

```bash
systemd-analyze security wplan.service | tail -3
```

Ожидается exposure около 1.5–2.5 («OK»). Если сервис падает с `SIGSYS` —
дело в `SystemCallFilter`; смотрите `journalctl -u wplan | grep -i seccomp` и
добавляйте недостающую группу вызовов, а не отключайте фильтр целиком.
Разбор остальных типовых сбоев — в `deploy/RUNBOOK-security-hardening.md`.

**Важно про часовой пояс:** `OnCalendar=` в таймерах и `DAY_START_CUTOFF_HOUR`
в `src/settings.py` (граница "начать"/"завершить" день) считаются в
**локальном времени VPS**, а офис — в `Europe/Moscow` (UTC+3). Шаблоны в
`deploy/*.timer` и `DAY_START_CUTOFF_HOUR=11` в `src/settings.py` уже
рассчитаны на то, что VPS работает в **UTC** (типичный дефолт для большинства
VPS-провайдеров) — 06:55/14:55 UTC = 09:55/17:55 MSK. Если ваш сервер в
другом часовом поясе — либо `timedatectl set-timezone Europe/Moscow` и
верните `OnCalendar=` к 09:55/17:55 + `DAY_START_CUTOFF_HOUR=14`, либо
пересчитайте оба под фактический пояс сервера сами.

### 9. Проверка

```bash
systemctl list-timers wplan-morning.timer wplan-evening.timer
systemctl show wplan.service -p User -p Group     # ожидается User=wplan
```

**Осторожно с ручным прогоном.** `systemctl start wplan.service` — не
безобидный smoke-test: он выполняет реальное действие с вашим рабочим днём.
В зависимости от текущего часа (`DAY_START_CUTOFF_HOUR`) он либо начнёт, либо
**завершит** день в WPlan. Если день уже открыт, а сейчас после границы —
ручной запуск закроет его раньше времени, и поправить придётся вручную через
веб-интерфейс. Повторный запуск не поможет: он вернёт `EDITING_NOT_AVAILABLE`.

```bash
systemctl start wplan.service
journalctl -u wplan.service -n 30 --no-pager
```

Ожидаемый лог: `Logging in` → `Login successful` →
`Fetched N absence record(s)` → либо пропуск (если сегодня отпуск/day-off),
либо `start_end_workday(is_start=...) -> ...` → `Done`.

`Login successful` заодно означает, что TLS-рукопожатие прошло с полной
проверкой цепочки против корпоративного CA: при неверном пиннинге здесь был бы
`CERTIFICATE_VERIFY_FAILED`.

Проверить, что в журнал не попадают секреты и логин (важно после любой правки
логирования):

```bash
journalctl -u wplan --since '-10min' --no-pager \
  | grep -E 'api\.telegram\.org/bot|@office\.lan' \
  && echo ">>> ПРОБЛЕМА: секрет или логин в журнале" || echo ">>> OK"
```

Ограничение по времени обязательно: без него grep поймает исторические записи
старых версий, где логин ещё писался в лог.

### Обновление кода на сервере

```bash
cp /opt/wplan/wplan-api /root/wplan-api.bak.$(date +%Y%m%d)   # бэкап перед обновлением

cd /opt/wplan-src && git pull
cd wplan && ~/.local/bin/poetry install

~/.local/bin/poetry run pytest -q                          # 20 passed
~/.local/bin/poetry run pyinstaller --clean --noconfirm wplan-api.spec
~/.local/bin/poetry run pyi-archive_viewer -l dist/wplan-api | grep -i pem

install -o root -g root -m 0755 dist/wplan-api /opt/wplan/wplan-api
```

(`systemctl restart` не нужен — юниты `oneshot`, подхватят новый бинарник на следующий запуск таймера. Пользователя `wplan` создавать повторно тоже не надо.)

Откат при проблеме — вернуть бэкап: `install -o root -g root -m 0755 /root/wplan-api.bak.YYYYMMDD /opt/wplan/wplan-api`.

Полный сценарий усиления безопасности на уже работающем сервере, с проверкой
после каждого шага и откатом, — в `deploy/RUNBOOK-security-hardening.md`.

## Структура проекта

```
main.py                    - точка входа: login -> проверка отсутствий -> start/end day -> Telegram
src/settings.py            - переменные окружения (+ systemd-creds на проде)
src/api/wplan_client.py    - GraphQL-клиент (aiohttp), TLS-пиннинг корпоративного CA
src/api/wplan-ca.pem       - корпоративная цепочка доверия (публичные сертификаты)
src/notify.py              - отправка уведомлений в Telegram (Bot API)
tests/                     - регрессионные тесты на находки аудита безопасности
wplan-api.spec             - PyInstaller-спек (вкладывает wplan-ca.pem в бинарь)
deploy/                    - шаблоны systemd-юнитов (сервис, таймеры, override для VPN)
deploy/RUNBOOK-*.md        - сценарий усиления безопасности на работающем сервере
```

Сборка — только через PyInstaller напрямую на целевом Linux-сервере
(кросс-компиляция не поддерживается, поэтому Docker для сборки не используется).

## Принятые решения по безопасности

Коротко, чтобы не пришлось выяснять заново:

- **TLS.** Доверяем только корпоративному корню из `src/api/wplan-ca.pem`,
  а не отключаем проверку. `ssl=False` возвращать нельзя — за этим следит тест.
- **Права.** Сервис работает от `wplan`, не от root. Секреты остаются
  `root:root 600`: их читает systemd, а не процесс.
- **Секреты в коде.** Пароль — через `systemd-creds`; остальное — через
  окружение. Хардкода в текущих `.py`-файлах нет. В историю репозитория ранее
  попадали собранные бинарники (см. комментарий в `.gitignore`) — это отдельный
  риск утечки через артефакт сборки, а не через исходники.
- **Логи.** В journald не пишутся Telegram-токен (он часть URL Bot API),
  корпоративный логин и ФИО сотрудника. `accessToken` не логируется никогда.
- **Внешние каналы.** В Telegram уходит только класс ошибки или коды
  GraphQL-ошибок — не текст исключения с внутренними хостнеймами и URL.
- **Зависимости.** Пиннинг через `poetry.lock`; проверять `pip-audit`.
