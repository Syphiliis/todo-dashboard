#!/bin/bash
# Start both Dashboard (gunicorn) and Telegram Bot
# Used by systemd service - if either process dies, both are killed and systemd restarts

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Launch gunicorn (dashboard)
python3 -m gunicorn -w 2 -b 0.0.0.0:5001 src.app:app &
GUNICORN_PID=$!

# Launch bot
python3 -m src.bot &
BOT_PID=$!

echo "Dashboard PID: $GUNICORN_PID | Bot PID: $BOT_PID"

# If either process exits, kill the other and exit (systemd will restart)
cleanup() {
    kill $GUNICORN_PID $BOT_PID 2>/dev/null
    wait
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for either to exit
while kill -0 $GUNICORN_PID 2>/dev/null && kill -0 $BOT_PID 2>/dev/null; do
    wait -n 2>/dev/null || sleep 1
done

echo "A process exited, shutting down..."
cleanup
