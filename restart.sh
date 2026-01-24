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

# 2. Tuer brutalement TOUS les processus résiduels (uniquement todo-dashboard)
echo "🛑 Nettoyage des processus..."

# Chemin fixe du projet sur le VPS
TODO_DIR="/home/ubuntu/todo-dashboard"

# Tuer Gunicorn
pkill -9 -f "gunicorn.*todo-dashboard" 2>/dev/null && echo "  - Processus Gunicorn tués"

# Tuer TOUS les processus Python app.py et bot.py liés à todo-dashboard
echo "  - Recherche de tous les processus todo-dashboard..."

# Méthode 1: pkill avec patterns multiples (plus robuste)
pkill -9 -f "todo-dashboard.*app.py" 2>/dev/null && echo "  - Anciens app.py tués (pkill pattern 1)"
pkill -9 -f "todo-dashboard.*bot.py" 2>/dev/null && echo "  - Anciens bot.py tués (pkill pattern 1)"
pkill -9 -f "$TODO_DIR/venv/bin/python.*app.py" 2>/dev/null && echo "  - Anciens app.py tués (pkill pattern 2)"
pkill -9 -f "$TODO_DIR/venv/bin/python.*bot.py" 2>/dev/null && echo "  - Anciens bot.py tués (pkill pattern 2)"

# Méthode 2: Recherche par cwd (processus dont le répertoire de travail est todo-dashboard)
for PID in $(pgrep -f "python.*app.py" 2>/dev/null); do
    if ls -l /proc/$PID/cwd 2>/dev/null | grep -q "todo-dashboard"; then
        kill -9 $PID 2>/dev/null && echo "  - app.py tué via cwd check: $PID"
    fi
done
for PID in $(pgrep -f "python.*bot.py" 2>/dev/null); do
    if ls -l /proc/$PID/cwd 2>/dev/null | grep -q "todo-dashboard"; then
        kill -9 $PID 2>/dev/null && echo "  - bot.py tué via cwd check: $PID"
    fi
done

# Méthode 3: Tuer par PIDs trouvés avec grep large
APP_PIDS=$(ps aux | grep -E "(todo-dashboard.*app\.py|app\.py.*todo-dashboard)" | grep -v grep | awk '{print $2}')
if [ ! -z "$APP_PIDS" ]; then
    echo "  - Processus app.py restants: $APP_PIDS"
    for PID in $APP_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

BOT_PIDS=$(ps aux | grep -E "(todo-dashboard.*bot\.py|bot\.py.*todo-dashboard)" | grep -v grep | awk '{print $2}')
if [ ! -z "$BOT_PIDS" ]; then
    echo "  - Processus bot.py restants: $BOT_PIDS"
    for PID in $BOT_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

# Libérer le port 5000 (avec fuser si disponible, sinon lsof)
if command -v fuser &> /dev/null; then
    fuser -k 5000/tcp 2>/dev/null && echo "  - Port 5000 libéré (fuser)"
else
    PORT_PID=$(lsof -ti:5000 2>/dev/null)
    if [ ! -z "$PORT_PID" ]; then
        kill -9 $PORT_PID && echo "  - Port 5000 libéré ($PORT_PID)"
    fi
fi

# Attendre que tout soit bien terminé
sleep 3

# Vérification finale
REMAINING=$(ps aux | grep -E "todo-dashboard.*(app|bot)\.py" | grep -v grep | wc -l)

if [ $REMAINING -eq 0 ]; then
    echo "✅ Tous les processus todo-dashboard ont été arrêtés"
else
    echo "⚠️  Attention: $REMAINING processus encore en cours"
    ps aux | grep -E "todo-dashboard.*(app|bot)\.py" | grep -v grep
fi



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
