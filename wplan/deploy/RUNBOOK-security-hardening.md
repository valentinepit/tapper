# Runbook: применение правок безопасности на VPS

Порядок применения исправлений из `wplan-security-review.md` на сервере.
Выполнять от root (или через `sudo`). Каждый шаг заканчивается проверкой —
не переходите к следующему, пока проверка не прошла.

Основание: H-1 (проверка TLS), H-2 + M-2 (запуск от non-root + hardening),
H-3 (утечка bot-токена в journald), M-4, L-1..L-5.

---

## 0. Перед началом: зафиксировать текущее состояние

```bash
systemctl list-timers 'wplan*' --all
cp /etc/systemd/system/wplan.service /root/wplan.service.bak
cp /opt/wplan/wplan-api /root/wplan-api.bak
```

Откат в конце документа.

Останавливаем таймеры, чтобы прогон не начался посреди обновления:

```bash
systemctl stop wplan-morning.timer wplan-evening.timer
systemctl disable wplan-morning.timer wplan-evening.timer
```

---

## 1. Обновить код и пересобрать бинарь

Важно: в этой версии появился новый файл `src/api/wplan-ca.pem`, который
PyInstaller обязан вложить внутрь бинаря (прописано в `wplan-api.spec`).
Без него собранный бинарь не сможет проверить сертификат и упадёт с понятной
ошибкой «Не найден файл доверенных сертификатов».

```bash
cd /opt/wplan-src
git fetch origin
git checkout without-interface
git pull --ff-only origin without-interface

cd wplan
~/.local/bin/poetry install --sync
```

Прогнать тесты перед сборкой — они проверяют именно правки безопасности:

```bash
~/.local/bin/poetry run pytest -q
```

Ожидается `20 passed`. Если упал `test_h1_ca_bundle_exists` — не подтянулся
`src/api/wplan-ca.pem`, проверьте `git status`.

Проверить, что известных уязвимостей в зависимостях нет:

```bash
~/.local/bin/poetry run pip install pip-audit
~/.local/bin/poetry run pip-audit
```

Сборка:

```bash
~/.local/bin/poetry run pyinstaller --clean --noconfirm wplan-api.spec
```

**Проверка, что сертификат реально попал внутрь бинаря.**

Внимание: искать в бинаре текст `BEGIN CERTIFICATE` бесполезно — PyInstaller
складывает `datas` в сжатый CArchive, и содержимое файлов в `strings` не
появляется даже когда всё вложено правильно. Открытым текстом в TOC лежит
только имя файла.

```bash
# быстрая проверка: имя файла в TOC
strings dist/wplan-api | grep -c 'wplan-ca.pem'          # ожидается >= 1

# авторитетная: список содержимого архива
~/.local/bin/poetry run pyi-archive_viewer -l dist/wplan-api | grep -i pem
```

Вторая команда должна показать строку, оканчивающуюся на
`'src/api/wplan-ca.pem'`. Если `pyi-archive_viewer` отсутствует:

```bash
~/.local/bin/poetry run python -c "
from PyInstaller.archive.readers import CArchiveReader
r = CArchiveReader('dist/wplan-api')
print([n for n in r.toc if 'pem' in n])
"
```

Ожидается `['src/api/wplan-ca.pem']`. Если пусто — сертификат не вложился,
разбираться с `datas` в `wplan-api.spec`.

---

## 2. Создать системного пользователя (H-2)

Утилита больше не должна работать от root.

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin wplan
id wplan
```

---

## 3. Установить бинарь с правильными правами

```bash
install -o root -g root -m 0755 dist/wplan-api /opt/wplan/wplan-api
ls -l /opt/wplan/wplan-api
```

Владелец root, а пользователь `wplan` только читает и исполняет — так сам
сервис не сможет подменить свой же бинарь.

---

## 4. Права на секреты (M-2)

Важно: после перехода на `User=wplan` права на секреты ослаблять НЕ нужно.
И `EnvironmentFile=`, и `LoadCredentialEncrypted=` обрабатывает сам systemd
от root ещё до сброса привилегий — процесс получает готовые переменные
окружения и расшифрованный credential в tmpfs, а сами файлы не читает.
Поэтому оставляем строгие `root:root 600`, а не `root:wplan 640`.

```bash
chown root:root /etc/wplan/wplan.env
chmod 600 /etc/wplan/wplan.env

chown root:root /etc/wplan/wplan_pass.cred
chmod 600 /etc/wplan/wplan_pass.cred

chown root:root /etc/wplan
chmod 700 /etc/wplan

ls -la /etc/wplan/
```

Проверка, что пользователь `wplan` действительно НЕ имеет доступа
(ожидается `Permission denied` — это правильный результат):

```bash
sudo -u wplan cat /etc/wplan/wplan.env
```

---

## 5. Перевыпустить Telegram bot-токен (H-3)

Старый токен мог осесть в journald в открытом виде — до этой правки он
попадал туда вместе с текстом исключения `ClientResponseError`.

1. В Telegram: **@BotFather** → `/mybots` → выбрать бота → `API Token` →
   **Revoke current token** → скопировать новый.
2. Заменить значение в `/etc/wplan/wplan.env` (строка `TELEGRAM_BOT_TOKEN=`).
3. Затереть старый токен в журнале — выборочно journald чистить не умеет,
   поэтому либо ротация целиком, либо смириться (токен уже отозван):

```bash
journalctl --rotate
journalctl --vacuum-time=1s
```

Проверить, что в актуальном журнале токенов не осталось:

```bash
journalctl -u wplan --no-pager | grep -c 'api.telegram.org/bot'
```

Должно быть `0`.

---

## 6. Установить hardened systemd-юнит (H-2 + M-2)

```bash
cd /opt/wplan-src/wplan
cp deploy/wplan.service /etc/systemd/system/wplan.service
sed -i 's/YOUR_VPN_CONFIG_NAME/<имя_вашего_ovpn_конфига>/' /etc/systemd/system/wplan.service
grep -n 'openvpn-client@' /etc/systemd/system/wplan.service
systemctl daemon-reload
```

Оценить итоговую изоляцию:

```bash
systemd-analyze security wplan.service
```

Ожидается exposure около 1.5–2.5 («OK»/«SAFE»). До правок было ~9.2 («UNSAFE»).

---

## 7. Пробный запуск

```bash
systemctl start wplan.service
systemctl status wplan.service --no-pager
journalctl -u wplan -n 50 --no-pager
```

**Что должно быть в журнале:** `Logging in`, `Logged in as ...`,
`Fetching absences`, и либо `start_end_workday(...) -> ...`, либо
`Day already in the requested state ... - nothing to do`.

**Чего в журнале быть НЕ должно:** строки `Logging in as <логин>@office.lan`
(убрано в L-2) и любых вхождений `api.telegram.org/bot` (H-3).

Проверка одной командой:

```bash
journalctl -u wplan --no-pager | grep -E 'api\.telegram\.org/bot|@office\.lan' && \
  echo "ПРОБЛЕМА: секрет или логин в журнале" || echo "OK: журнал чист"
```

### Если запуск упал

**`SIGSYS` / `seccomp`** — слишком строгий `SystemCallFilter`:

```bash
journalctl -u wplan --no-pager | grep -i -E 'seccomp|SIGSYS'
```

Временно закомментируйте `SystemCallFilter=@system-service` в юните,
проверьте, что дело в нём, и вместо полного отключения добавьте
недостающую группу (например `SystemCallFilter=@system-service @mount`).

**`Read-only file system`** — `ProtectSystem=strict`. PyInstaller
распаковывается в `/tmp`, а `PrivateTmp=yes` его туда пускает. Если всё же
нужен путь на запись, добавьте `ReadWritePaths=/путь`.

**`Не найден файл доверенных сертификатов`** — сертификат не вложился
в бинарь, вернитесь к проверке в шаге 1.

**`CERTIFICATE_VERIFY_FAILED`** — сертификат wplan перевыпущен другим CA.
Снять цепочку заново (нужен доступ к wplan с сервера):

```bash
openssl s_client -showcerts -connect wplan.office.lan:443 </dev/null 2>/dev/null \
  | awk '/BEGIN CERT/,/END CERT/'
```

и обновить `src/api/wplan-ca.pem` (оставить два последних блока — SUB-CA и root).

**`Failed to load environment files`** — файл `/etc/wplan/wplan.env`
недоступен самому systemd. Проверьте, что владелец `root:root` и путь
существует; на права `600` systemd не жалуется, он читает их от root.

---

## 8. Включить таймеры обратно

```bash
systemctl enable --now wplan-morning.timer wplan-evening.timer
systemctl list-timers 'wplan*' --all --no-pager
```

Сверьте `NEXT` с ожидаемым временем по Москве (в таймерах стоит UTC:
06:55 UTC = 09:55 MSK, `RandomizedDelaySec=600`).

---

## 9. Финальная проверка

```bash
# от кого работает сервис
systemctl show wplan.service -p User -p Group

# уровень изоляции
systemd-analyze security wplan.service | tail -3

# TLS-проверка включена: сертификат вложен в бинарь
strings /opt/wplan/wplan-api | grep -c 'wplan-ca.pem'

# секретов в журнале нет
journalctl -u wplan --no-pager | grep -cE 'api\.telegram\.org/bot|@office\.lan'

# права на секреты
ls -la /etc/wplan/
```

Ожидаемо: `User=wplan`, exposure ниже 3, вхождений `wplan-ca.pem` ≥1,
вхождений секретов `0`, права `600 root:root` на файлы в `/etc/wplan`.

---

## Откат

```bash
systemctl stop wplan-morning.timer wplan-evening.timer wplan.service
cp /root/wplan.service.bak /etc/systemd/system/wplan.service
cp /root/wplan-api.bak /opt/wplan/wplan-api
chown root:root /etc/wplan/wplan.env && chmod 600 /etc/wplan/wplan.env
systemctl daemon-reload
systemctl enable --now wplan-morning.timer wplan-evening.timer
```

Учтите: откат возвращает `ssl=False`, работу от root и утечку токена
в журнал. Пользуйтесь им только чтобы восстановить работоспособность,
и возвращайтесь к разбору причины.
