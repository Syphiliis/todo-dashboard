#!/bin/bash
# Script pour tuer toutes les instances du bot Telegram

echo "🛑 Arrêt de TOUTES les instances du bot..."

# Trouver tous les processus bot.py
BOT_PIDS=$(ps aux | grep "python.*bot.py" | grep -v grep | awk '{print $2}')

if [ -z "$BOT_PIDS" ]; then
    echo "✅ Aucune instance du bot en cours d'exécution"
else
    echo "📋 Instances trouvées: $BOT_PIDS"
    for PID in $BOT_PIDS; do
        echo "  - Arrêt du processus $PID..."
        kill -9 $PID
    done
    echo "✅ Toutes les instances ont été arrêtées"
fi

# Attendre un peu
sleep 2

# Vérifier qu'il n'y a plus rien
REMAINING=$(ps aux | grep "python.*bot.py" | grep -v grep | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo "✅ Confirmation: aucun bot en cours d'exécution"
    
    # Relancer une seule instance
    echo "🚀 Démarrage d'une nouvelle instance du bot..."
    cd /home/ubuntu/todo-dashboard
    source venv/bin/activate
    nohup python3 bot.py > bot.log 2>&1 &
    NEW_PID=$!
    echo "✅ Bot démarré avec PID: $NEW_PID"
else
    echo "⚠️  Attention: $REMAINING processus restants détectés"
    ps aux | grep "python.*bot.py" | grep -v grep
fi
