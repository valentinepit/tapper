#!/bin/bash

export WPLAN_LOGIN="YOUR_WPLAN_LOGIN"
export WPLAN_PASS="YOUR_WPLAN_PASS"
echo "=== Запуск wplan в $(date) ===" >> ~/wplan_cron.log
echo $WPLAN_PASS

/YOUR_PATH/wplan.sh 2>&1 | tee -a ~/wplan_cron.log

echo "=== Завершено с кодом $? ===" >> ~/wplan_cron.log
EOF

