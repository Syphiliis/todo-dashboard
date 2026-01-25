import json
from datetime import datetime

from src.config import CLAUDE_MODEL
from src.db import get_db
from src.services.ai_client import get_claude_client


def generate_daily_content() -> None:
    claude = get_claude_client()
    if not claude:
        return

    today = datetime.now().date().isoformat()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM daily_content WHERE date = ?', (today,))
    if cursor.fetchone():
        conn.close()
        return

    try:
        prompt = """Génère en JSON:
{
  \"quote\": \"citation inspirante sur la tech, IA, productivité ou entrepreneuriat (max 120 chars)\",
  \"author\": \"auteur de la citation\",
  \"fun_fact\": \"fait intéressant sur tech, science ou histoire (max 150 chars)\"
}

Sois concis, impactant, en français."""

        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system="Tu génères du contenu quotidien inspirant et éducatif. Réponds uniquement en JSON valide.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()

        data = json.loads(text)

        cursor.execute('''
            INSERT INTO daily_content (date, quote, quote_author, fun_fact)
            VALUES (?, ?, ?, ?)
        ''', (today, data['quote'], data['author'], data['fun_fact']))
        conn.commit()
    finally:
        conn.close()
