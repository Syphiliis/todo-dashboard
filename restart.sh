#!/bin/bash
# Script de redémarrage complet pour Todo Dashboard & Bot
# Ce script arrête TOUS les services (systemd, gunicorn, python) et relance tout proprement.

echo "🔄 Redémarrage COMPLET des services Todo Dashboard..."

# 1. Arrêter le service systemd s'il existe
if systemctl list-units --full -all | grep -q "todo-dashboard.service"; then
    echo "🛑 Arrêt du service systemd 'todo-dashboard'..."
    sudo systemctl stop todo-dashboard
    sudo systemctl disable todo-dashboard
    echo "  - Service systemd arrêté et désactivé"
fi

# 2. Tuer brutalement les processus résiduels
echo "🛑 Nettoyage des processus..."

# Tuer Gunicorn
pkill -f "gunicorn" && echo "  - Processus Gunicorn tués"

# Tuer Python app/bot
pkill -f "python3 app.py" && echo "  - Anciens app.py tués"
pkill -f "python3 bot.py" && echo "  - Anciens bot.py tués"

# Tuer tout processus sur le port 5000
PORT_PID=$(lsof -ti:5000)
if [ ! -z "$PORT_PID" ]; then
    kill -9 $PORT_PID && echo "  - Processus sur port 5000 tué ($PORT_PID)"
fi

# Attendre un peu
sleep 2

# 3. Mise à jour et dépendances
echo "📦 Vérification dépendances..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# 4. Lancer Dashboard
echo "🚀 Démarrage Dashboard (port 5000)..."
nohup python3 app.py > app.log 2>&1 &
APP_PID=$!
echo "  PID: $APP_PID"

# 5. Lancer Bot Telegram
echo "🤖 Démarrage Bot Telegram..."
nohup python3 bot.py > bot.log 2>&1 &
BOT_PID=$!
echo "  PID: $BOT_PID"

echo "✅ Tout est redémarré proprement via ce script!"
echo "📝 Logs via: tail -f app.log -f bot.log"
