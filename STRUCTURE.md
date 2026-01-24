# Project Structure

This project follows a modular structure where source code is separated from configuration, scripts, and static assets.

## Root Directory

- `src/`: Contains all the Python source code for the application and the bot.
- `web/`: (If applicable) Frontend code if separated (currently static assets are in `static/` or managed via Flask).
- `scripts/`: Helper scripts for maintenance or one-off tasks (none yet, but convention).
- `data/`: Storage for SQLite database and other data files.
- `static/`: Static assets (HTML, CSS, JS) served by Flask.
- `venv/`: Python virtual environment (ignored by git).
- `*.sh`: Deployment and management scripts (`restart.sh`, `deploy.sh`).
- `requirements.txt`: Python dependencies.

## Source Code (`src/`)

- `src/app.py`: The main Flask application entry point. Handles API requests and serves the dashboard.
- `src/bot.py`: The Telegram bot entry point. Handles Telegram updates and interacts with the API.
- `src/agents/`: Directory containing AI agent modules.
    - `src/agents/assistant_agent.py`: Agent logic for handling general queries and task analysis.
    - `src/agents/content_agent.py`: Agent logic for content generation.

## How to Run

### Local Development / Manual Restart

Use the provided script to restart all services:

```bash
./restart.sh
```

This script will:
1. Stop existing processes (`src.app` and `src.bot`).
2. Update dependencies.
3. Start the Dashboard (`src.app`) on port 5000.
4. Start the Telegram Bot (`src.bot`).

### Manual Execution

To run components individually from the root directory:

**Dashboard:**
```bash
python3 -m src.app
```

**Telegram Bot:**
```bash
python3 -m src.bot
```

### Deployment (Systemd)

The project is deployed using `systemd`. The `deploy.sh` script configures the service.

The service runs gunicorn with the module syntax:
```bash
gunicorn -w 2 -b 0.0.0.0:5000 src.app:app
```
