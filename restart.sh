#!/bin/bash
# Script de redémarrage rapide pour Todo Dashboard & Bot

echo "🔄 Redémarrage des services Todo Dashboard..."

# 1. Tuer les processus existants
echo "🛑 Arrêt des processus existants..."
pkill -f "python3 app.py" && echo "  - app.py arrêté" || echo "  - app.py n'était pas lancé"
pkill -f "python3 bot.py" && echo "  - bot.py arrêté" || echo "  - bot.py n'était pas lancé"

# Attendre un peu
sleep 2

# 2. Activer venv et mise à jour
echo "📦 Vérification dépendances..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# 3. Lancer Dashboard
echo "🚀 Démarrage Dashboard (port 5000)..."
nohup python3 app.py > app.log 2>&1 &
APP_PID=$!
echo "  PID: $APP_PID"

# 4. Lancer Bot Telegram
echo "🤖 Démarrage Bot Telegram..."
nohup python3 bot.py > bot.log 2>&1 &
BOT_PID=$!
echo "  PID: $BOT_PID"

echo "✅ Tout est redémarré!"
echo "📝 Logs via: tail -f app.log -f bot.log"
