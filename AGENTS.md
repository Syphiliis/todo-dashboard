# AI Agents

All agents use Claude Haiku via `src/services/ai_client.py`. Intent detection in `bot.py` is pattern-based (no API call).

## Assistant Agent (`src/agents/assistant_agent.py`)

Personal productivity assistant. Telegram commands: `/briefing`, `/emails`.
- Daily briefing: pending tasks, priorities, deadlines
- Email summary via Gmail API
- Task analysis: structures vague requests into actionable tasks
- Calendar events via Google Calendar API

## Content Agent (`src/agents/content_agent.py`)

Social media content generator. Telegram command: `/content <subject>`.
- Twitter/X (280 chars) + LinkedIn (1300 chars) drafts
- Brand contexts: **EasyNode** (sovereign AI, GPU/LLM infra, technical tone), **Souverain AI** (thought leadership, visionary tone)

## Task Assistant (inline in `bot.py`)

Conversational task creation from natural language.
- Extracts: title, category, priority, time estimate, 3-5 action steps
- Categories: easynode, immobilier, content, personnel, admin
- Priorities: urgent, important, normal
- Flow: user describes task → Claude proposes structured task → user confirms → POST to `/api/todos`

## Adding a New Agent

1. Create `src/agents/<name>_agent.py`, use `from src.services.ai_client import get_claude_response`
2. Register command handler in `bot.py` via `application.add_handler(CommandHandler(...))`
3. Document in this file
