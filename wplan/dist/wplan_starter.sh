#!/bin/bash

export WPLAN_LOGIN="YOUR LOGIN"
export WPLAN_PASS="YOUR PASSWORD"
echo "=== Запуск wplan в $(date) ===" >> ~/wplan_cron.log

/YOUR PATH/wplan.sh 2>&1 | tee -a ~/wplan_cron.log

echo "=== Завершено с кодом $? ===" >> ~/wplan_cron.log
EOF

