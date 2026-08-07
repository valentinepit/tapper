# WPLAN — автоматический старт/конец рабочего дня через API

Раньше это делалось через Selenium (эмуляция браузера). Сейчас `main.py` дёргает
GraphQL API `wplan.office.lan` напрямую (без браузера): логинится, смотрит,
не отпуск/day-off ли сегодня, и если рабочий день — жмёт кнопку начала или
конца дня (в зависимости от времени суток).

## Как это работает

`main.py` → `src/api/WplanApiClient`:
1. `login(username, password)` — GraphQL mutation `Login`.
2. `get_absences()` — GraphQL query `AbsenceRequestAllPersonal`, весь список отпусков/day-off'ов без фильтра.
3. Если сегодняшняя дата попадает в один из периодов из шага 2 — ничего не делаем.
4. Иначе `start_end_workday(is_start=...)` — GraphQL mutation `StartOrFinishDay`. `is_start` определяется по времени суток (`DAY_START_CUTOFF_HOUR` в `main.py`, по умолчанию до 14:00 — начать день, после — завершить).

Ошибка сервера `EDITING_NOT_AVAILABLE` ("день уже был начат/завершён ранее") —
не баг, а штатная ситуация (кто-то/что-то уже переключил день); код логирует
её как INFO и завершается без ошибки.

## Переменные окружения

| Переменная | Что это | Секрет? |
|---|---|---|
| `WPLAN_LOGIN` | логин (вида `login@office.lan`) | нет |
| `WPLAN_PASS` | пароль | **да** |
| `LOGIN_QUERY_HASH` | persisted-query хэш mutation `Login` | нет |
| `VACATIONS_QUERY_HASH` | хэш query `PersonalVacationsByWorkingDays` | нет |
| `START_FINISH_QUERY_HASH` | хэш mutation `StartOrFinishDay` | нет |
| `ABSENCES_QUERY_HASH` | хэш query `AbsenceRequestAllPersonal` | нет |

Хэши — это Apollo persisted-query sha256 конкретного деплоя wplan (одинаковые
для всех сотрудников одной компании, не персональные секреты). Если у вас
другой инстанс wplan и хэши не совпадают — снимите свои через
DevTools → Network при логине/клике на сайте (см. `operationName`,
`extensions.persistedQuery.sha256Hash` в запросах к `/ru-RU/api/graphql`).

`wplan.office.lan` резолвится и открывается только из корпоративной сети —
для запуска откуда-либо ещё нужен VPN-туннель в эту сеть.

## Локальный запуск (разработка)

1. `poetry install`
2. Скопировать `.env.example` (в корне репозитория, на уровень выше `wplan/`) в `.env` и вписать свои `WPLAN_LOGIN`/`WPLAN_PASS` (хэши там уже настоящие, менять не нужно, если это тот же деплой wplan).
3. `poetry run python main.py`

Локально быть в корпоративной сети (или подключённым к её VPN) обязательно —
иначе `wplan.office.lan` не резолвится.

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

Проверка:

```bash
getent hosts wplan.office.lan
curl -k -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 5 https://wplan.office.lan/
```

### 3. Python / Poetry / код

```bash
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/valentinepit/tapper.git /opt/wplan-src
cd /opt/wplan-src && git checkout without-interface
cd wplan
~/.local/bin/poetry install
```

### 4. Сборка бинарника

PyInstaller не кросс-компилирует — собирайте прямо на целевом сервере (не на macOS/Windows с последующим копированием):

```bash
~/.local/bin/poetry run pyinstaller wplan-api.spec
mkdir -p /opt/wplan
cp dist/wplan-api /opt/wplan/wplan-api
chmod +x /opt/wplan/wplan-api
```

### 5. Секреты

Несекретные значения (логин + 4 хэша) — в `/etc/wplan/wplan.env`:

```bash
mkdir -p /etc/wplan
cat > /etc/wplan/wplan.env
```

Впишите (свои значения, `Ctrl+D` в конце):

```
WPLAN_LOGIN=your_login@office.lan
LOGIN_QUERY_HASH=...
VACATIONS_QUERY_HASH=...
START_FINISH_QUERY_HASH=...
ABSENCES_QUERY_HASH=...
```

```bash
chown root:root /etc/wplan/wplan.env
chmod 600 /etc/wplan/wplan.env
```

Пароль — отдельно, зашифрован через `systemd-creds` (не лежит на диске в
открытом виде; расшифровывается только самим systemd прямо перед запуском
сервиса, в tmpfs, не в файле):

```bash
systemd-creds encrypt --name=wplan_pass - /etc/wplan/wplan_pass.cred
# ввести пароль, затем Ctrl+D
chmod 600 /etc/wplan/wplan_pass.cred
```

### 6. systemd-сервис и таймеры

```bash
cp deploy/wplan.service /etc/systemd/system/wplan.service
sed -i 's/YOUR_VPN_CONFIG_NAME/<name>/' /etc/systemd/system/wplan.service
cp deploy/wplan-morning.timer deploy/wplan-evening.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now wplan-morning.timer wplan-evening.timer
```

**Важно про часовой пояс:** `OnCalendar=` в таймерах и `DAY_START_CUTOFF_HOUR`
в `src/settings.py` (граница "начать"/"завершить" день) считаются в
**локальном времени VPS**, а офис — в `Europe/Moscow` (UTC+3). Шаблоны в
`deploy/*.timer` и `DAY_START_CUTOFF_HOUR=11` в `src/settings.py` уже
рассчитаны на то, что VPS работает в **UTC** (типичный дефолт для большинства
VPS-провайдеров) — 06:55/14:55 UTC = 09:55/17:55 MSK. Если ваш сервер в
другом часовом поясе — либо `timedatectl set-timezone Europe/Moscow` и
верните `OnCalendar=` к 09:55/17:55 + `DAY_START_CUTOFF_HOUR=14`, либо
пересчитайте оба под фактический пояс сервера сами.

### 7. Проверка

```bash
systemctl list-timers wplan-morning.timer wplan-evening.timer
systemctl start wplan.service   # ручной прогон
journalctl -u wplan.service -n 30
```

Ожидаемый лог: `Logged in as ...` → `Fetched N absence record(s)` → либо
пропуск (если сегодня отпуск/day-off), либо
`start_end_workday(is_start=...) -> ...`.

### Обновление кода на сервере

```bash
cd /opt/wplan-src && git pull
cd wplan && ~/.local/bin/poetry install
~/.local/bin/poetry run pyinstaller wplan-api.spec
cp dist/wplan-api /opt/wplan/wplan-api
```
(`systemctl restart` не нужен — юниты `oneshot`, подхватят новый бинарник на следующий запуск таймера.)

## Структура проекта

```
main.py                 - точка входа: login -> проверка отсутствий -> start/end day
src/settings.py         - переменные окружения (+ systemd-creds на проде)
src/api/wplan_client.py - GraphQL-клиент (aiohttp)
wplan-api.spec          - PyInstaller-спек для сборки бинарника
deploy/                 - шаблоны systemd-юнитов (сервис, таймеры, override для VPN)
```
