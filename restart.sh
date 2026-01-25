#!/bin/bash
# Script de redémarrage complet pour Todo Dashboard & Bot
# Ce script arrête TOUS les services (systemd, gunicorn, python) et relance tout proprement.

echo "🔄 Redémarrage COMPLET des services Todo Dashboard..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TODO_DIR="$SCRIPT_DIR"
DCA_DIR="$TODO_DIR/dca"
DCA_PORT="${DCA_PORT:-3000}"
DCA_PID_FILE="$DCA_DIR/dca.pid"
DCA_LOG="$TODO_DIR/dca.log"

cd "$SCRIPT_DIR" || exit 1

# 1. Arrêter le service systemd s'il existe
if systemctl list-units --full -all | grep -q "todo-dashboard.service"; then
    echo "🛑 Arrêt du service systemd 'todo-dashboard'..."
    sudo systemctl stop todo-dashboard
    sudo systemctl disable todo-dashboard
    echo "  - Service systemd arrêté et désactivé"
fi

# 2. Tuer brutalement TOUS les processus résiduels (uniquement todo-dashboard)
echo "🛑 Nettoyage des processus..."

# Tuer Gunicorn
pkill -9 -f "gunicorn.*todo-dashboard" 2>/dev/null && echo "  - Processus Gunicorn tués"

# Tuer TOUS les processus Python src.app et src.bot liés à todo-dashboard
echo "  - Recherche de tous les processus todo-dashboard..."

# Méthode 1: pkill avec patterns multiples (plus robuste)
pkill -9 -f "todo-dashboard.*src.app" 2>/dev/null && echo "  - Anciens src.app tués (pkill pattern 1)"
pkill -9 -f "todo-dashboard.*src.bot" 2>/dev/null && echo "  - Anciens src.bot tués (pkill pattern 1)"
pkill -9 -f "$TODO_DIR/venv/bin/python.*src.app" 2>/dev/null && echo "  - Anciens src.app tués (pkill pattern 2)"
pkill -9 -f "$TODO_DIR/venv/bin/python.*src.bot" 2>/dev/null && echo "  - Anciens src.bot tués (pkill pattern 2)"

# Méthode 2: Recherche par cwd (processus dont le répertoire de travail est todo-dashboard)
for PID in $(pgrep -f "python.*src.app" 2>/dev/null); do
    if ls -l /proc/$PID/cwd 2>/dev/null | grep -q "todo-dashboard"; then
        kill -9 $PID 2>/dev/null && echo "  - src.app tué via cwd check: $PID"
    fi
done
for PID in $(pgrep -f "python.*src.bot" 2>/dev/null); do
    if ls -l /proc/$PID/cwd 2>/dev/null | grep -q "todo-dashboard"; then
        kill -9 $PID 2>/dev/null && echo "  - src.bot tué via cwd check: $PID"
    fi
done

# Méthode 3: Tuer par PIDs trouvés avec grep large
APP_PIDS=$(ps aux | grep -E "(todo-dashboard.*src\.app|src\.app.*todo-dashboard)" | grep -v grep | awk '{print $2}')
if [ ! -z "$APP_PIDS" ]; then
    echo "  - Processus src.app restants: $APP_PIDS"
    for PID in $APP_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

BOT_PIDS=$(ps aux | grep -E "(todo-dashboard.*src\.bot|src\.bot.*todo-dashboard)" | grep -v grep | awk '{print $2}')
if [ ! -z "$BOT_PIDS" ]; then
    echo "  - Processus src.bot restants: $BOT_PIDS"
    for PID in $BOT_PIDS; do
        kill -9 $PID 2>/dev/null && echo "    Tué: $PID"
    done
fi

# Arrêter le serveur DCA (Next.js)
if [ -d "$DCA_DIR" ]; then
    if [ -f "$DCA_PID_FILE" ]; then
        DCA_PID=$(cat "$DCA_PID_FILE")
        if ps -p "$DCA_PID" > /dev/null 2>&1; then
            kill -9 "$DCA_PID" 2>/dev/null && echo "  - Serveur DCA arrêté: $DCA_PID"
        fi
        rm -f "$DCA_PID_FILE"
    fi
fi

# Libérer le port DCA
if [ -d "$DCA_DIR" ]; then
    if command -v fuser &> /dev/null; then
        fuser -k "$DCA_PORT"/tcp 2>/dev/null && echo "  - Port DCA $DCA_PORT libéré (fuser)"
    else
        PORT_PID=$(lsof -ti:"$DCA_PORT" 2>/dev/null)
        if [ ! -z "$PORT_PID" ]; then
            kill -9 "$PORT_PID" && echo "  - Port DCA $DCA_PORT libéré ($PORT_PID)"
        fi
    fi
fi

# Libérer le port 5001 (avec fuser si disponible, sinon lsof)
if command -v fuser &> /dev/null; then
    fuser -k 5001/tcp 2>/dev/null && echo "  - Port 5001 libéré (fuser)"
else
    PORT_PID=$(lsof -ti:5001 2>/dev/null)
    if [ ! -z "$PORT_PID" ]; then
        kill -9 $PORT_PID && echo "  - Port 5001 libéré ($PORT_PID)"
    fi
fi

# Attendre que tout soit bien terminé
sleep 3

# Vérification finale
REMAINING=$(ps aux | grep -E "todo-dashboard.*src\.(app|bot)" | grep -v grep | wc -l)

if [ $REMAINING -eq 0 ]; then
    echo "✅ Tous les processus todo-dashboard ont été arrêtés"
else
    echo "⚠️  Attention: $REMAINING processus encore en cours"
    ps aux | grep -E "todo-dashboard.*src\.(app|bot)" | grep -v grep
fi



# 3. Mise à jour et dépendances
echo "📦 Vérification dépendances..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# DCA - dépendances/build
if [ -d "$DCA_DIR" ]; then
    echo "📦 Vérification dépendances DCA..."
    if command -v npm &> /dev/null; then
        if [ ! -d "$DCA_DIR/node_modules" ]; then
            (cd "$DCA_DIR" && npm install)
        fi
        if [ ! -d "$DCA_DIR/.next" ]; then
            (cd "$DCA_DIR" && npm run build)
        fi
    else
        echo "⚠️  npm non installé, DCA ignoré"
    fi
fi

# 4. Lancer Dashboard
echo "🚀 Démarrage Dashboard (port 5001)..."
nohup python3 -m src.app > app.log 2>&1 &
APP_PID=$!
echo "  PID: $APP_PID"

# 5. Lancer Bot Telegram
echo "🤖 Démarrage Bot Telegram..."
nohup python3 -m src.bot > bot.log 2>&1 &
BOT_PID=$!
echo "  PID: $BOT_PID"

# 6. Lancer DCA
if [ -d "$DCA_DIR" ]; then
    echo "📈 Démarrage DCA (port $DCA_PORT)..."
    if command -v node &> /dev/null; then
        (
            cd "$DCA_DIR" || exit 1
            nohup node node_modules/next/dist/bin/next start -p "$DCA_PORT" > "$DCA_LOG" 2>&1 &
            echo $! > "$DCA_PID_FILE"
        )
        if [ -f "$DCA_PID_FILE" ]; then
            DCA_PID=$(cat "$DCA_PID_FILE")
            echo "  PID: $DCA_PID"
        fi
    else
        echo "⚠️  Node.js non installé, DCA non démarré"
    fi
fi

echo "✅ Tout est redémarré proprement via ce script!"
echo "📝 Logs via: tail -f app.log -f bot.log -f dca.log"
