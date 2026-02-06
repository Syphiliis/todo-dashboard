# Alex Todo Dashboard

Personal productivity management system combining a modern web dashboard, an intelligent Telegram bot, and AI-powered agents using Claude.

## Features

### Web Dashboard
- **Task Management**: Full CRUD operations with priority levels (urgent/important/normal)
- **iOS-style Design**: Modern, professional UI with light/dark mode support
- **Multiple Views**: Dashboard, Projects, Archives, Calendar
- **Productivity Analytics**: 7-day streak tracking, category breakdown, best day stats
- **Habits Tracking**: Daily habit completion with 30-day history visualization
- **Daily Content**: AI-generated quotes and fun facts

### Telegram Bot
- **Natural Language Processing**: Understands French & English task descriptions
- **Smart Task Analysis**: Automatically extracts title, category, priority, time estimate
- **Step-by-step Guides**: Generates actionable steps for each task
- **Daily Briefing**: Summarizes tasks, emails (Gmail), and productivity stats
- **Content Generation**: Creates social media posts for Twitter/X and LinkedIn
- **Proactive Reminders**: Deadline alerts 1 hour before due, daily recap at 7 PM

### AI Agents (Claude)
- **Assistant Agent**: Daily briefings, email summaries, calendar integration
- **Content Agent**: Social media content for EasyNode & Souverain AI brands
- **Task Assistant**: Intelligent task structuring with time estimates

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+, Flask |
| Database | SQLite |
| AI | Anthropic Claude API (Haiku for cost optimization) |
| Bot | python-telegram-bot v21 |
| Scheduler | APScheduler |
| Production | Gunicorn, systemd |
| Frontend | Vanilla JS, CSS, iOS-like Design System |

## Quick Start

### Prerequisites
- Python 3.9+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Anthropic API Key

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/todo-dashboard.git
cd todo-dashboard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens
```

### Configuration (.env)

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ANTHROPIC_API_KEY=sk-ant-your_api_key
CLAUDE_MODEL=claude-haiku-4-5-20251001
DATABASE_PATH=./data/todos.db
PORT=5001
TIMEZONE=Europe/Paris
DASHBOARD_ACCESS_TOKEN=optional_secret_for_auth
```

### Running

```bash
# Development (restarts all services)
./restart.sh

# Or run components individually
python3 -m src.app    # Dashboard on port 5001
python3 -m src.bot    # Telegram bot
```

### Production Deployment

```bash
chmod +x deploy.sh
./deploy.sh
sudo systemctl restart todo-dashboard
```

## Project Structure

```
todo-dashboard/
├── src/                      # Core Python source
│   ├── app.py               # Flask API & dashboard server
│   ├── bot.py               # Telegram bot with AI integration
│   ├── config.py            # Environment configuration
│   ├── db.py                # Database initialization
│   ├── agents/              # AI agent modules
│   │   ├── assistant_agent.py
│   │   └── content_agent.py
│   └── services/            # Utility services
│       ├── ai_client.py     # Claude API wrapper
│       ├── telegram.py      # Telegram message sender
│       ├── daily_content.py # Daily quote/fact generator
│       └── reminders.py     # Deadline checks & recap
├── static/                  # Frontend assets
│   ├── index.html          # Main dashboard
│   ├── styles/             # iOS-like design system
│   └── js/                 # Theme switcher
├── data/                   # SQLite database
├── requirements.txt        # Python dependencies
├── restart.sh             # Dev restart script
└── deploy.sh              # Production deployment
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/todos` | List tasks (filterable by status, category, archived) |
| POST | `/api/todos` | Create task |
| PUT | `/api/todos/:id` | Update task |
| DELETE | `/api/todos/:id` | Delete task |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/analytics` | 7-day productivity insights |
| GET | `/api/habits` | Habit tracking with history |
| GET | `/api/roadmap` | Long-term goals |
| POST | `/api/notify` | Send custom Telegram notification |

### API Examples

```bash
# Create a task
curl -X POST http://localhost:5001/api/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Review PR", "category": "easynode", "priority": "urgent"}'

# Mark as completed
curl -X PUT http://localhost:5001/api/todos/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/briefing` | Daily briefing (tasks + emails) |
| `/list` | List pending tasks |
| `/add <task>` | Add task with AI analysis |
| `/done <id>` | Mark task as complete |
| `/stats` | Dashboard statistics |
| `/roadmap` | Long-term goals |
| `/content <subject>` | Generate social media content |
| `/help` | Command reference |

## Database Schema

- **todos**: Task storage (title, description, category, priority, status, deadline)
- **categories**: Predefined categories with emojis & colors
- **roadmap_items**: Strategic goals (mid-term/long-term)
- **daily_content**: Cached quotes & fun facts
- **habits** / **habit_tracking**: Habit tracking system
- **projects**: Project management
- **task_history**: Analytics cache

## Documentation

- [STRUCTURE.md](./STRUCTURE.md) - Detailed project structure
- [AGENTS.md](./AGENTS.md) - AI agents implementation
- [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) - UI/UX design tokens
- [DEPLOY.md](./DEPLOY.md) - Deployment guide
- [CLAUDE.md](./CLAUDE.md) - Development instructions for Claude

## Related Projects & Resources

### Similar Projects
- [TeleAdminPanel](https://github.com/Zeeshanahmad4/TeleAdminPanel-Advanced-Telegram-Bot-Administration) - Telegram bot administration dashboard
- [telegram-bot-template](https://github.com/donBarbos/telegram-bot-template) - Production template with admin panel
- [MyTaskBot](https://github.com/MyTaskBot/MyTaskBot) - Task manager bot for Telegram

### Claude Code Resources
- [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code) - Skills, hooks, and plugins
- [Awesome Agent Skills](https://github.com/VoltAgent/awesome-agent-skills) - 200+ agent skills from official teams
- [Claude Skill Telegram](https://github.com/AlexSKuznetsov/claude-skill-telegram) - Send messages and schedule reminders
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices) - Official Anthropic guide

### Telegram Bot Development
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/) - Official documentation
- [JobQueue Documentation](https://docs.python-telegram-bot.org/en/v21.5/telegram.ext.jobqueue.html) - APScheduler integration

## Security

- Optional token-based dashboard authentication
- Telegram chat ID verification
- Parameterized SQL queries
- Environment variables for sensitive keys
- HTTPS-ready for reverse proxy deployment

## Future Roadmap

- [ ] Recurring task patterns
- [ ] Multi-user support
- [ ] Habit streak notifications
- [ ] Advanced analytics dashboard
- [ ] Mobile app integration
- [ ] Slack integration

## License

MIT License - Created for Alexandre | [EasyNode](https://easynode.ai)
