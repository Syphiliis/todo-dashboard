# Project Structure

```
src/
├── app.py                  # Flask API & dashboard (port 5001)
├── bot.py                  # Telegram bot + AI integration
├── config.py               # .env loader
├── db.py                   # SQLite init & connection
├── agents/
│   ├── assistant_agent.py  # Briefings, emails, task analysis
│   └── content_agent.py    # Social media content generation
└── services/
    ├── ai_client.py        # Claude API wrapper
    ├── telegram.py         # Telegram message sender
    ├── daily_content.py    # Quote/fact generator & cache
    └── reminders.py        # Deadline checks, daily recap

static/
├── index.html              # Main dashboard
├── projects.html           # Project management
├── archives.html           # Archived tasks
├── dca.html                # DCA iframe wrapper
├── styles/
│   ├── design-system.css   # CSS variables, colors, typography
│   ├── components.css      # Buttons, cards, inputs, badges
│   ├── utilities.css       # Spacing, flex helpers
│   └── animations.css      # Transitions, keyframes
└── js/
    └── theme-switcher.js   # Light/dark mode toggle

data/todos.db               # SQLite — tables: todos, categories, projects,
                            # roadmap_items, daily_content, habits,
                            # habit_tracking, task_history
dca/                        # Next.js DCA app (port 3000)
```
