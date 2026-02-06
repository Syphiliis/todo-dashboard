# CLAUDE.md

Flask + Telegram + SQLite todo dashboard. DB: `data/todos.db`, port 5001.

## Commands

```bash
python3 -m src.app      # Run dashboard
python3 -m src.bot      # Run Telegram bot
./restart.sh             # Restart all services
./deploy.sh              # Production deploy
```

## Rules

- Always use parameterized SQL queries (never f-strings/format in SQL)
- Frontend: vanilla JS only, no frameworks. Use CSS vars from `design-system.css`
- Python: use module syntax (`python3 -m src.app`), not direct file execution
- After changing entry points, verify `restart.sh` compatibility
- Use Haiku subagents for simple/isolated tasks to save costs
- Respond in the same language the user uses

## Context files

Read these only when relevant: `STRUCTURE.md` (file layout), `AGENTS.md` (AI agent specs), `DESIGN_SYSTEM.md` (UI tokens)
