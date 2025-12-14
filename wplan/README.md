Из dist копируем себе wplan.sh

Создаем файл wplan_starter.sh
Или копируем его из dist

После этого редактируем свой крон командой crontab -e

Для первичного теста - каждые 5 минут
*/5 * * * * /PATH_TO_WPLAN/wplan_starter.sh

для запуска на вкл выкл два раза в день
0 10 * * 1-5 /Users/valentin/wplan_cron.sh
0 19 * * 1-4 /Users/valentin/wplan_cron.sh

Все работает!!
Если хочется убрать окошко браузера, то нужно поставить в main.py в 11 строке Debug = False