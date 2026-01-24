# AI Agents

This project uses AI agents to enhance productivity and automate tasks.

## Agent Architecture

Agents are located in `src/agents/`. They are designed to be modular and task-specific.

### Assistant Agent (`src/agents/assistant_agent.py`)

**Role**: Personal productivity assistant.

**Capabilities**:
- **Briefing**: Generates a daily briefing based on tasks and calendar.
- **Email Summary**: Checks emails (via Gmail API) and provides a summary.
- **Task Analysis**: Helps structure vague tasks into actionable items with time estimates and priorities.

**Usage**:
Invoked by `src/bot.py` via the `/briefing` and `/emails` commands, or when analyzing complex task requests.

### Content Agent (`src/agents/content_agent.py`)

**Role**: Social media content generator.

**Capabilities**:
- **Content Generation**: Creates tweets, LinkedIn posts, or other content based on a subject.
- **Tone Adaptation**: Adapts tone for different platforms (e.g., professional for LinkedIn, concise for Twitter).

**Usage**:
Invoked by `src/bot.py` via the `/content` command.

## Adding a New Agent

1. Create a new python file in `src/agents/`, e.g., `src/agents/research_agent.py`.
2. Define a class or functions that encapsulate the agent's logic.
3. Import and use the agent in `src/bot.py` or `src/app.py`.
4. Ensure dependencies are added to `requirements.txt`.
