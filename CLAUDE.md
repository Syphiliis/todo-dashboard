# CLAUDE.md

Instructions for working on the **Alex Todo Dashboard** project.

---

## Agent Selection

| Agent | Use Case |
|-------|----------|
| Opus | **Planning**: Major refactoring, Architecture changes, Complex agent logic |
| Sonnet | **Execution**: Python/Flask implementation, Debugging, Script updates |
| Haiku | **Fast Tasks**: Quick fixes, Typos, Simple logic updates |

---

## Expected Behavior

- **Language**: Respond in **English** (or French if context demands, but code/comments in English/French mix is consistent with current codebase).
- **Verification**: Read files before editing. Verify paths are correct (especially after refactoring to `src/`).
- **Quality**: Code must work with the `src/` modular structure. Run from root.
- **Efficiency**: Use `python3 -m src.module` syntax for execution.

---

## Communication

- Be concise.
- Explain structural changes clearly.
- Always check `restart.sh` compatibility when changing entry points.

---

## 📚 Available Documentation

- **STRUCTURE.md**: Detailed project structure and file locations.
- **AGENTS.md**: Specifics about the AI agents' roles and implementation.
- **DEPLOY.md**: Deployment instructions (legacy/general).

---

## Tech Stack

### 🐍 Backend - `src/`
- **Language**: Python 3.9+
- **Framework**: Flask
- **WSGI**: Gunicorn (Production)
- **Database**: SQLite (`data/todos.db`)
- **Main Entry**: `src/app.py`

### 🤖 Bot - `src/`
- **Library**: `python-telegram-bot`
- **AI**: Anthropic Claude API
- **Entry**: `src/bot.py`

### 🛠 Scripts
- `restart.sh`: Main dev/restart script.
- `deploy.sh`: Systemd setup script.

---

## Common Commands

### Execution (from Root)

- **Run Dashboard**: `python3 -m src.app`
- **Run Bot**: `python3 -m src.bot`
- **Restart All**: `./restart.sh`

### Testing
- Manual testing via Telegram bot and Web Dashboard.

---

## Project Structure (Summary)

- `src/`: Core logic (App & Bot)
    - `src/agents/`: AI Agents
- `data/`: Database
- `static/`: Frontend assets
- Root: Configuration and Scripts

---

## Recent Changes (Refactoring Jan 2026)

- Moved all python source to `src/`.
- Updated `restart.sh` and `deploy.sh` to use module syntax (`-m src.app`).
- Added strict `__init__.py` usage for package management.
