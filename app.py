#!/usr/bin/env python3
"""
Alex Todo Dashboard - Backend API
Dashboard personnel avec notifications Telegram
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/todos.db')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Ensure data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            deadline DATETIME,
            reminder_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            emoji TEXT DEFAULT '📋',
            color TEXT DEFAULT '#6366f1'
        );

        -- Insert default categories
        INSERT OR IGNORE INTO categories (name, emoji, color) VALUES
            ('easynode', '🚀', '#3b82f6'),
            ('immobilier', '🏠', '#10b981'),
            ('personnel', '👤', '#8b5cf6'),
            ('content', '📱', '#f59e0b'),
            ('admin', '📄', '#6b7280');
    ''')
    conn.commit()
    conn.close()


def send_telegram_message(message):
    """Send a message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def check_deadlines():
    """Check for upcoming deadlines and send reminders."""
    conn = get_db()
    cursor = conn.cursor()

    # Find todos with deadlines in the next hour that haven't been reminded
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


# Initialize scheduler for deadline checks
scheduler = BackgroundScheduler()
scheduler.add_job(check_deadlines, 'interval', minutes=15)
scheduler.start()


# ============== API Routes ==============

@app.route('/')
def index():
    """Serve the dashboard."""
    return send_from_directory('static', 'index.html')


@app.route('/api/todos', methods=['GET'])
def get_todos():
    """Get all todos with optional filters."""
    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')
    category = request.args.get('category')

    query = 'SELECT * FROM todos WHERE 1=1'
    params = []

    if status:
        query += ' AND status = ?'
        params.append(status)
    if category:
        query += ' AND category = ?'
        params.append(category)

    query += ' ORDER BY CASE priority WHEN "urgent" THEN 1 WHEN "important" THEN 2 ELSE 3 END, deadline ASC'

    cursor.execute(query, params)
    todos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(todos)


@app.route('/api/todos', methods=['POST'])
def create_todo():
    """Create a new todo."""
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO todos (title, description, category, priority, deadline)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data.get('title'),
        data.get('description'),
        data.get('category', 'general'),
        data.get('priority', 'normal'),
        data.get('deadline')
    ))

    todo_id = cursor.lastrowid
    conn.commit()

    # Send Telegram notification for new task
    priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(data.get('priority', 'normal'), '⚪')
    message = f"""📝 <b>Nouvelle tâche ajoutée</b>

{priority_emoji} <b>{data.get('title')}</b>
📁 {data.get('category', 'general')}"""

    if data.get('deadline'):
        message += f"\n⏳ Deadline: {data.get('deadline')}"

    send_telegram_message(message)

    cursor.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
    todo = dict(cursor.fetchone())
    conn.close()

    return jsonify(todo), 201


@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update a todo."""
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    # Build dynamic update query
    updates = []
    params = []

    for field in ['title', 'description', 'category', 'priority', 'status', 'deadline']:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])

    if 'status' in data and data['status'] == 'completed':
        updates.append('completed_at = ?')
        params.append(datetime.now().isoformat())

    updates.append('updated_at = ?')
    params.append(datetime.now().isoformat())

    params.append(todo_id)

    cursor.execute(f'''
        UPDATE todos SET {', '.join(updates)} WHERE id = ?
    ''', params)

    conn.commit()

    # Send notification if task completed
    if data.get('status') == 'completed':
        cursor.execute('SELECT title FROM todos WHERE id = ?', (todo_id,))
        todo = cursor.fetchone()
        if todo:
            send_telegram_message(f"✅ <b>Tâche terminée!</b>\n\n{todo['title']}\n\n<i>Bravo Alexandre! 🎉</i>")

    cursor.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
    todo = dict(cursor.fetchone())
    conn.close()

    return jsonify(todo)


@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a todo."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories')
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(categories)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard statistics."""
    conn = get_db()
    cursor = conn.cursor()

    # Total counts
    cursor.execute('SELECT COUNT(*) as total FROM todos')
    total = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as completed FROM todos WHERE status = "completed"')
    completed = cursor.fetchone()['completed']

    cursor.execute('SELECT COUNT(*) as pending FROM todos WHERE status = "pending"')
    pending = cursor.fetchone()['pending']

    # Today's tasks
    today = datetime.now().date().isoformat()
    cursor.execute('''
        SELECT COUNT(*) as today_completed
        FROM todos
        WHERE status = "completed"
        AND date(completed_at) = ?
    ''', (today,))
    today_completed = cursor.fetchone()['today_completed']

    # Overdue tasks
    cursor.execute('''
        SELECT COUNT(*) as overdue
        FROM todos
        WHERE status = "pending"
        AND deadline < ?
    ''', (datetime.now().isoformat(),))
    overdue = cursor.fetchone()['overdue']

    conn.close()

    completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

    return jsonify({
        'total': total,
        'completed': completed,
        'pending': pending,
        'today_completed': today_completed,
        'overdue': overdue,
        'completion_rate': completion_rate
    })


@app.route('/api/notify', methods=['POST'])
def send_notification():
    """Send a custom Telegram notification."""
    data = request.json
    message = data.get('message', '')

    if send_telegram_message(message):
        return jsonify({'success': True})
    return jsonify({'success': False}), 500


@app.route('/api/daily-summary', methods=['POST'])
def send_daily_summary():
    """Send daily summary via Telegram."""
    conn = get_db()
    cursor = conn.cursor()

    # Get pending tasks
    cursor.execute('''
        SELECT title, category, priority, deadline
        FROM todos
        WHERE status = "pending"
        ORDER BY CASE priority WHEN "urgent" THEN 1 WHEN "important" THEN 2 ELSE 3 END
        LIMIT 10
    ''')
    pending = cursor.fetchall()

    # Get today's completed
    today = datetime.now().date().isoformat()
    cursor.execute('''
        SELECT COUNT(*) as count FROM todos
        WHERE status = "completed" AND date(completed_at) = ?
    ''', (today,))
    completed_today = cursor.fetchone()['count']

    conn.close()

    # Build message
    message = f"""📊 <b>Résumé du {datetime.now().strftime('%d/%m/%Y')}</b>

✅ Tâches complétées aujourd'hui: <b>{completed_today}</b>
📋 Tâches en attente: <b>{len(pending)}</b>

"""

    if pending:
        message += "<b>Prochaines priorités:</b>\n"
        for todo in pending[:5]:
            priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(todo['priority'], '⚪')
            message += f"{priority_emoji} {todo['title']}\n"

    message += "\n<i>Bonne continuation Alexandre! 💪</i>"

    if send_telegram_message(message):
        return jsonify({'success': True})
    return jsonify({'success': False}), 500


# Initialize database on startup
init_db()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
