Из dist копируем себе wplan.sh

Создаем файл wplan_starter.sh

#!/bin/bash
export WPLAN_LOGIN="YOUR LOGIN"
export WPLAN_PASS="YOUR PASSWORD"
echo "=== Запуск wplan в $(date) ===" >> ~/wplan_cron.log
echo $WPLAN_PASS

/PATH_TO_WPLAN/wplan.sh 2>&1 | tee -a ~/wplan_cron.log

echo "=== Завершено с кодом $? ===" >> ~/wplan_cron.log
EOF

После этого редактируем свой крон командой crontab -e

Для первичного теста - каждые 5 минут
*/5 * * * * /PATH_TO_WPLAN/wplan_starter.sh

для запуска на вкл выкл два раза в день
0 10 * * 1-5 /Users/valentin/wplan_cron.sh
0 19 * * 1-4 /Users/valentin/wplan_cron.sh