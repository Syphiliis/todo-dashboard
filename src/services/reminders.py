from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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


def record_daily_stats() -> None:
    """Record daily task stats into task_history for analytics."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        today = datetime.now().date().isoformat()

        cursor.execute(
            'SELECT COUNT(*) as count FROM todos WHERE status = "completed" AND date(completed_at) = ?',
            (today,)
        )
        completed = cursor.fetchone()['count']

        cursor.execute(
            'SELECT COUNT(*) as count FROM todos WHERE date(created_at) = ?',
            (today,)
        )
        created = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM todos WHERE status = "pending"')
        pending = cursor.fetchone()['count']

        cursor.execute('''
            INSERT INTO task_history (date, completed_count, created_count, pending_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                completed_count = excluded.completed_count,
                created_count = excluded.created_count,
                pending_count = excluded.pending_count
        ''', (today, completed, created, pending))

        conn.commit()
        conn.close()
    except Exception:
        pass


def send_daily_recap() -> None:
    # Record stats before sending recap
    record_daily_stats()

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


RECURRENCE_DELTAS = {
    'daily': timedelta(days=1),
    'weekdays': timedelta(days=1),  # special handling below
    'weekly': timedelta(weeks=1),
    'biweekly': timedelta(weeks=2),
    'monthly': relativedelta(months=1),
}


def spawn_recurring_tasks() -> None:
    """Check completed recurring tasks and create the next occurrence."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        now = datetime.now()

        cursor.execute('''
            SELECT * FROM todos
            WHERE recurrence_pattern IS NOT NULL
            AND status = 'completed'
            AND recurrence_pattern != ''
        ''')
        tasks = [dict(row) for row in cursor.fetchall()]

        for task in tasks:
            pattern = task['recurrence_pattern']
            completed_at = datetime.fromisoformat(task['completed_at']) if task.get('completed_at') else now

            delta = RECURRENCE_DELTAS.get(pattern)
            if not delta:
                continue

            next_date = completed_at + delta

            # Weekdays: skip Saturday/Sunday
            if pattern == 'weekdays':
                while next_date.weekday() >= 5:  # 5=Sat, 6=Sun
                    next_date += timedelta(days=1)

            # Check recurrence_end_date
            if task.get('recurrence_end_date'):
                end_date = datetime.fromisoformat(task['recurrence_end_date'])
                if next_date > end_date:
                    continue

            # Only spawn if next_date has been reached
            if next_date > now:
                continue

            # Check if a pending copy already exists (avoid duplicates)
            cursor.execute('''
                SELECT COUNT(*) as count FROM todos
                WHERE title = ? AND status = 'pending' AND recurrence_pattern = ?
            ''', (task['title'], pattern))
            if cursor.fetchone()['count'] > 0:
                continue

            # Create fresh copy
            cursor.execute('''
                INSERT INTO todos (title, description, category, priority, deadline, recurrence_pattern, recurrence_end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                task['title'],
                task.get('description'),
                task.get('category', 'general'),
                task.get('priority', 'normal'),
                next_date.isoformat() if task.get('deadline') else None,
                pattern,
                task.get('recurrence_end_date')
            ))

        conn.commit()
        conn.close()
    except Exception:
        pass
