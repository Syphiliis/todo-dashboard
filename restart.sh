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

# Obtenir le chemin absolu du dossier actuel
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Tuer Gunicorn (seulement si dans ce dossier)
pkill -9 -f "gunicorn.*$SCRIPT_DIR" && echo "  - Processus Gunicorn tués"

# Tuer TOUS les processus Python app.py et bot.py (avec -9 pour forcer)
echo "  - Recherche de tous les processus Python dans $SCRIPT_DIR..."

# Méthode 1: pkill avec -9 (force kill) - filtre par chemin
pkill -9 -f "$SCRIPT_DIR.*app.py" && echo "  - Anciens app.py tués (pkill)"
pkill -9 -f "$SCRIPT_DIR.*bot.py" && echo "  - Anciens bot.py tués (pkill)"

# Méthode 2: Trouver et tuer manuellement tous les PIDs restants (filtre par chemin)
APP_PIDS=$(ps aux | grep "python.*$SCRIPT_DIR.*app.py" | grep -v grep | awk '{print $2}')
if [ ! -z "$APP_PIDS" ]; then
    echo "  - Processus app.py restants trouvés: $APP_PIDS"
    for PID in $APP_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

BOT_PIDS=$(ps aux | grep "python.*$SCRIPT_DIR.*bot.py" | grep -v grep | awk '{print $2}')
if [ ! -z "$BOT_PIDS" ]; then
    echo "  - Processus bot.py restants trouvés: $BOT_PIDS"
    for PID in $BOT_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

# Tuer tout processus sur le port 5000
PORT_PID=$(lsof -ti:5000 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    kill -9 $PORT_PID && echo "  - Processus sur port 5000 tué ($PORT_PID)"
fi

# Attendre que tout soit bien terminé
sleep 3

# Vérification finale (uniquement pour ce dossier)
REMAINING_BOTS=$(ps aux | grep "python.*$SCRIPT_DIR.*bot.py" | grep -v grep | wc -l)
REMAINING_APPS=$(ps aux | grep "python.*$SCRIPT_DIR.*app.py" | grep -v grep | wc -l)

if [ $REMAINING_BOTS -eq 0 ] && [ $REMAINING_APPS -eq 0 ]; then
    echo "✅ Tous les processus todo-dashboard ont été arrêtés"
else
    echo "⚠️  Attention: $REMAINING_BOTS bot(s) et $REMAINING_APPS app(s) encore en cours dans $SCRIPT_DIR"
    ps aux | grep "python.*$SCRIPT_DIR.*\(app\|bot\).py" | grep -v grep
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
