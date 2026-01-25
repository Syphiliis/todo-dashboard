from datetime import datetime, timedelta

from src.db import get_db
from src.services.telegram import send_telegram_message


def check_deadlines() -> None:
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    soon = now + timedelta(hours=1)

    cursor.execute('''
        SELECT id, title, category, priority, deadline
        FROM todos
        WHERE status = 'pending'
        AND deadline IS NOT NULL
        AND deadline <= ?
        AND deadline >= ?
        AND reminder_sent = 0
    ''', (soon.isoformat(), now.isoformat()))

    todos = cursor.fetchall()

    for todo in todos:
        priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(todo['priority'], '⚪')
        message = f"""⏰ <b>Rappel - Deadline proche!</b>

{priority_emoji} <b>{todo['title']}</b>
📁 Catégorie: {todo['category']}
⏳ Deadline: {todo['deadline']}

<i>Il est temps de finaliser cette tâche!</i>"""

        if send_telegram_message(message):
            cursor.execute('UPDATE todos SET reminder_sent = 1 WHERE id = ?', (todo['id'],))

    conn.commit()
    conn.close()


def send_daily_recap() -> None:
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM todos WHERE status = "pending"')
        pending = cursor.fetchone()['total']

        today = datetime.now().date().isoformat()
        cursor.execute('SELECT COUNT(*) as count FROM todos WHERE status = "completed" AND date(completed_at) = ?', (today,))
        completed_today = cursor.fetchone()['count']

        cursor.execute('''
            SELECT title, priority FROM todos
            WHERE status = "pending"
            ORDER BY CASE priority WHEN "urgent" THEN 1 WHEN "important" THEN 2 ELSE 3 END
            LIMIT 5
        ''')
        priorities = cursor.fetchall()

        cursor.execute('SELECT quote, quote_author FROM daily_content WHERE date = ?', (today,))
        daily = cursor.fetchone()

        conn.close()

        message = f"""📊 <b>Récap du {datetime.now().strftime('%d/%m/%Y')}</b>

✅ Tâches complétées aujourd'hui: <b>{completed_today}</b>
📋 Tâches en attente: <b>{pending}</b>

"""

        if priorities:
            message += "<b>Prochaines priorités:</b>\n"
            for p in priorities:
                emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(p['priority'], '⚪')
                message += f"{emoji} {p['title']}\n"
            message += "\n"

        if daily:
            message += f"💭 <i>\"{daily['quote']}\"</i>\n— {daily['quote_author']}\n\n"

        message += "<i>Bonne soirée Alexandre! 💪</i>"

        send_telegram_message(message)
    except Exception:
        pass
