#!/bin/bash

export WPLAN_LOGIN="YOUR_WPLAN_LOGIN"
export WPLAN_PASS="YOUR_WPLAN_PASS"
VPN_SERVICE="intra.ovpn"
echo "=== Запуск wplan в $(date) ===" >> ~/wplan_cron.log

echo "Проверяю VPN подключение..." | tee -a ~/wplan_cron.log

VPN_STATUS=$(networksetup -showpppoestatus "$VPN_SERVICE")
echo "Статус VPN '$VPN_SERVICE': $VPN_STATUS" | tee -a ~/wplan_cron.log

if [ "$VPN_STATUS" = "connected" ]; then
    echo "✅ VPN '$VPN_SERVICE' уже подключен" | tee -a ~/wplan_cron.log
else
    echo "⚠️  VPN '$VPN_SERVICE' не подключен, пытаюсь подключить..." | tee -a ~/wplan_cron.log
    
    networksetup -connectpppoeservice "$VPN_SERVICE"
    
    echo "Ожидаю подключения VPN..." | tee -a ~/wplan_cron.log
    sleep 10
    
    NEW_STATUS=$(networksetup -showpppoestatus "$VPN_SERVICE")
    echo "Новый статус VPN: $NEW_STATUS" | tee -a ~/wplan_cron.log
    
    if [ "$NEW_STATUS" = "connected" ]; then
        echo "✅ VPN успешно подключен" | tee -a ~/wplan_cron.log
    else
        echo "❌ Не удалось подключить VPN" | tee -a ~/wplan_cron.log
    fi
fi

echo "Проверяю доступность wplan.ru..." | tee -a ~/wplan_cron.log
if ping -c 1 -t 5 wplan.ru > /dev/null 2>&1; then
    echo "✅ wplan.ru доступен" | tee -a ~/wplan_cron.log
else
    echo "⚠️  wplan.ru недоступен" | tee -a ~/wplan_cron.log
fi

echo "Запускаю wplan..." | tee -a ~/wplan_cron.log
/PATH/wplan.sh 2>&1 | tee -a ~/wplan_cron.log

echo "=== Завершено с кодом $? ===" >> ~/wplan_cron.log

