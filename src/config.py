import os
from dotenv import load_dotenv

load_dotenv()

APP_VERSION = '2.1.0'

DATABASE_PATH = os.getenv('DATABASE_PATH', './data/todos.db')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
DASHBOARD_ACCESS_TOKEN = os.getenv('DASHBOARD_ACCESS_TOKEN')

DASHBOARD_API_URL = os.getenv('DASHBOARD_API_URL', 'http://localhost:5001/api')
DASHBOARD_PUBLIC_URL = os.getenv('DASHBOARD_PUBLIC_URL')

TIMEZONE = os.getenv('TIMEZONE', 'Europe/Paris')
DCA_BACKEND_URL = os.getenv('DCA_BACKEND_URL', 'http://84.46.253.225:8000/analyze')
DCA_APP_URL = os.getenv('DCA_APP_URL', 'http://127.0.0.1:3000')
PORT = int(os.getenv('PORT', '5001'))
