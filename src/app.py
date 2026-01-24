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
import anthropic

load_dotenv()

app = Flask(__name__, static_folder='../static')
CORS(app)

# Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/todos.db')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')

# Security: Token for dashboard access (optional)
DASHBOARD_ACCESS_TOKEN = os.getenv('DASHBOARD_ACCESS_TOKEN')  # None = no protection

# Claude client
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

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

        CREATE TABLE IF NOT EXISTS roadmap_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT DEFAULT 'mid_term',
            status TEXT DEFAULT 'in_progress',
            target_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS daily_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            quote TEXT NOT NULL,
            quote_author TEXT,
            fun_fact TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Insert default categories
        INSERT OR IGNORE INTO categories (name, emoji, color) VALUES
            ('easynode', '🚀', '#3b82f6'),
            ('immobilier', '🏠', '#10b981'),
            ('personnel', '👤', '#8b5cf6'),
            ('content', '📱', '#f59e0b'),
            ('admin', '📄', '#6b7280');

        -- Historique pour analytics de productivité
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            completed_count INTEGER DEFAULT 0,
            created_count INTEGER DEFAULT 0,
            pending_count INTEGER DEFAULT 0
        );

        -- Habitudes journalières
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '✅',
            frequency TEXT DEFAULT 'daily',
            target_count INTEGER DEFAULT 1,
            color TEXT DEFAULT '#10b981',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Suivi des habitudes
        CREATE TABLE IF NOT EXISTS habit_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            completed INTEGER DEFAULT 0,
            UNIQUE(habit_id, date)
        );
    ''')
    
    # Add recurrence columns if not exist (safe migration)
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN recurrence_pattern TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN recurrence_end_date DATE')
    except:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN parent_todo_id INTEGER')
    except:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN archived INTEGER DEFAULT 0')
    except:
        pass
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


def send_daily_recap():
    """Send daily recap via Telegram at 7 PM."""
    try:
        # Get stats
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM todos WHERE status = "pending"')
        pending = cursor.fetchone()['total']
        
        today = datetime.now().date().isoformat()
        cursor.execute('SELECT COUNT(*) as count FROM todos WHERE status = "completed" AND date(completed_at) = ?', (today,))
        completed_today = cursor.fetchone()['count']
        
        # Get top priorities
        cursor.execute('''
            SELECT title, priority FROM todos
            WHERE status = "pending"
            ORDER BY CASE priority WHEN "urgent" THEN 1 WHEN "important" THEN 2 ELSE 3 END
            LIMIT 5
        ''')
        priorities = cursor.fetchall()
        
        # Get daily content
        cursor.execute('SELECT quote, quote_author FROM daily_content WHERE date = ?', (today,))
        daily = cursor.fetchone()
        
        conn.close()
        
        # Build message
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
        print(f"Daily recap sent at {datetime.now()}")
    except Exception as e:
        print(f"Error sending daily recap: {e}")


def generate_daily_content():
    """Generate daily quote and fun fact using Claude."""
    if not claude:
        print("Claude API not configured")
        return
    
    today = datetime.now().date().isoformat()
    
    # Check if content already exists for today
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM daily_content WHERE date = ?', (today,))
    if cursor.fetchone():
        conn.close()
        print("Daily content already generated for today")
        return
    
    try:
        # Generate quote and fun fact
        prompt = """Génère en JSON:
{
  "quote": "citation inspirante sur la tech, IA, productivité ou entrepreneuriat (max 120 chars)",
  "author": "auteur de la citation",
  "fun_fact": "fait intéressant sur tech, science ou histoire (max 150 chars)"
}

Sois concis, impactant, en français."""
        
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system="Tu génères du contenu quotidien inspirant et éducatif. Réponds uniquement en JSON valide.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = response.content[0].text.strip()
        # Clean markdown if present
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()
        
        data = json.loads(text)
        
        # Insert into database
        cursor.execute('''
            INSERT INTO daily_content (date, quote, quote_author, fun_fact)
            VALUES (?, ?, ?, ?)
        ''', (today, data['quote'], data['author'], data['fun_fact']))
        conn.commit()
        conn.close()
        
        print(f"Daily content generated for {today}")
    except Exception as e:
        conn.close()
        print(f"Error generating daily content: {e}")


# Initialize database FIRST
init_db()

# Initialize scheduler
scheduler = BackgroundScheduler(timezone='Europe/Paris')
scheduler.add_job(check_deadlines, 'interval', minutes=15)
scheduler.add_job(send_daily_recap, 'cron', hour=19, minute=0)  # 7 PM daily
scheduler.add_job(generate_daily_content, 'cron', hour=6, minute=0)  # 6 AM daily
scheduler.start()

# Generate content on startup if needed
generate_daily_content()


# ============== Security ==============

@app.before_request
def check_dashboard_access():
    """Check access token for dashboard pages (not API)."""
    # Skip if no token configured (open access)
    if not DASHBOARD_ACCESS_TOKEN:
        return None
    
    # Skip API endpoints (bot needs unrestricted access)
    if request.path.startswith('/api/'):
        return None
    
    # Skip static files
    if request.path.startswith('/static/'):
        return None
    
    # Skip login page itself
    if request.path == '/login' or request.path == '/auth':
        return None
    
    # Check token in query params or cookie
    token = request.args.get('token') or request.cookies.get('dashboard_token')
    if token != DASHBOARD_ACCESS_TOKEN:
        # Redirect to login page instead of showing error
        from flask import redirect, url_for
        return redirect(url_for('login'))
    
    return None


# ============== API Routes ==============

@app.route('/login')
def login():
    """Login page for token authentication."""
    return '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔒 Alex Todo Dashboard - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        p {
            color: #666;
            margin-bottom: 30px;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #555;
            margin-bottom: 8px;
            font-weight: 500;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔒 Dashboard Login</h1>
        <p>Entre ton token d'accès</p>
        
        <div class="error" id="error">Token invalide</div>
        
        <form id="loginForm">
            <div class="input-group">
                <label for="token">Token d'accès</label>
                <input type="password" id="token" name="token" placeholder="Entre ton token secret" required autofocus>
            </div>
            <button type="submit">🚀 Accéder au Dashboard</button>
        </form>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const token = document.getElementById('token').value;
            const error = document.getElementById('error');
            
            try {
                const response = await fetch('/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                
                if (response.ok) {
                    window.location.href = '/';
                } else {
                    error.style.display = 'block';
                    setTimeout(() => error.style.display = 'none', 3000);
                }
            } catch (err) {
                error.textContent = 'Erreur de connexion';
                error.style.display = 'block';
            }
        });
    </script>
</body>
</html>
    '''


@app.route('/auth', methods=['POST'])
def authenticate():
    """Authenticate with token and set cookie."""
    data = request.json
    token = data.get('token')
    
    if token == DASHBOARD_ACCESS_TOKEN:
        response = jsonify({'success': True})
        response.set_cookie('dashboard_token', DASHBOARD_ACCESS_TOKEN, max_age=86400, httponly=True)
        return response
    
    return jsonify({'success': False}), 401


@app.route('/')
def index():
    """Serve the dashboard."""
    response = send_from_directory(app.static_folder, 'index.html')
    # Set cookie if valid token in URL (for subsequent requests)
    if DASHBOARD_ACCESS_TOKEN and request.args.get('token') == DASHBOARD_ACCESS_TOKEN:
        response.set_cookie('dashboard_token', DASHBOARD_ACCESS_TOKEN, max_age=86400, httponly=True)
    return response


@app.route('/api/todos', methods=['GET'])
def get_todos():
    """Get all todos with optional filters."""
    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')
    category = request.args.get('category')
    archived = request.args.get('archived')

    query = 'SELECT * FROM todos WHERE 1=1'
    params = []

    if archived == '1':
        query += ' AND archived = 1'
    elif archived == '0':
        query += ' AND archived = 0'
    else:
        # Default behavior: hide archived unless specifically requested
        query += ' AND archived = 0'

    if status and status != 'all':
        query += ' AND status = ?'
        params.append(status)
    if category and category != 'all':
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

    for field in ['title', 'description', 'category', 'priority', 'status', 'deadline', 'archived']:
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

    cursor.execute("SELECT COUNT(*) as completed FROM todos WHERE status = 'completed'")
    completed = cursor.fetchone()['completed']

    cursor.execute("SELECT COUNT(*) as pending FROM todos WHERE status = 'pending'")
    pending = cursor.fetchone()['pending']

    # Today's tasks
    today = datetime.now().date().isoformat()
    cursor.execute('''
        SELECT COUNT(*) as today_completed
        FROM todos
        WHERE status = 'completed'
        AND date(completed_at) = ?
    ''', (today,))
    today_completed = cursor.fetchone()['today_completed']

    # Overdue tasks
    cursor.execute('''
        SELECT COUNT(*) as overdue
        FROM todos
        WHERE status = 'pending'
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
    send_daily_recap()
    return jsonify({'success': True})


# ============== ROADMAP ENDPOINTS ==============

@app.route('/api/roadmap', methods=['GET'])
def get_roadmap():
    """Get all roadmap items with optional type filter."""
    conn = get_db()
    cursor = conn.cursor()
    
    item_type = request.args.get('type')
    
    query = 'SELECT * FROM roadmap_items WHERE 1=1'
    params = []
    
    if item_type:
        query += ' AND type = ?'
        params.append(item_type)
    
    query += ' ORDER BY target_date ASC, created_at DESC'
    
    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(items)


@app.route('/api/roadmap', methods=['POST'])
def create_roadmap_item():
    """Create a new roadmap item."""
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO roadmap_items (title, description, type, target_date, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data.get('title'),
        data.get('description'),
        data.get('type', 'mid_term'),
        data.get('target_date'),
        data.get('status', 'in_progress')
    ))
    
    item_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute('SELECT * FROM roadmap_items WHERE id = ?', (item_id,))
    item = dict(cursor.fetchone())
    conn.close()
    
    return jsonify(item), 201


@app.route('/api/roadmap/<int:item_id>', methods=['PUT'])
def update_roadmap_item(item_id):
    """Update a roadmap item."""
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    for field in ['title', 'description', 'type', 'status', 'target_date']:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])
    
    if 'status' in data and data['status'] == 'completed':
        updates.append('completed_at = ?')
        params.append(datetime.now().isoformat())
    
    updates.append('updated_at = ?')
    params.append(datetime.now().isoformat())
    
    params.append(item_id)
    
    cursor.execute(f'''
        UPDATE roadmap_items SET {', '.join(updates)} WHERE id = ?
    ''', params)
    
    conn.commit()
    
    cursor.execute('SELECT * FROM roadmap_items WHERE id = ?', (item_id,))
    item = dict(cursor.fetchone())
    conn.close()
    
    return jsonify(item)


@app.route('/api/roadmap/<int:item_id>', methods=['DELETE'])
def delete_roadmap_item(item_id):
    """Delete a roadmap item."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM roadmap_items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


# ============== DAILY CONTENT ENDPOINTS ==============

@app.route('/api/daily-content', methods=['GET'])
def get_daily_content():
    """Get today's quote and fun fact."""
    today = datetime.now().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM daily_content WHERE date = ?', (today,))
    content = cursor.fetchone()
    conn.close()
    
    if content:
        return jsonify(dict(content))
    
    # Generate if not exists
    generate_daily_content()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM daily_content WHERE date = ?', (today,))
    content = cursor.fetchone()
    conn.close()
    
    if content:
        return jsonify(dict(content))
    
    return jsonify({'error': 'Could not generate daily content'}), 500


@app.route('/api/daily-content/generate', methods=['POST'])
def regenerate_daily_content():
    """Force regenerate daily content."""
    today = datetime.now().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM daily_content WHERE date = ?', (today,))
    conn.commit()
    conn.close()
    
    generate_daily_content()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM daily_content WHERE date = ?', (today,))
    content = cursor.fetchone()
    conn.close()
    
    if content:
        return jsonify(dict(content))
    
    return jsonify({'error': 'Could not generate daily content'}), 500


# ============== VUE JOURNALIÈRE ==============

@app.route('/api/todos/today', methods=['GET'])
def get_today_todos():
    """Get today's tasks sorted by priority."""
    conn = get_db()
    cursor = conn.cursor()
    
    today = datetime.now().date().isoformat()
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    
    # Tasks due today OR pending with high priority
    cursor.execute('''
        SELECT * FROM todos
        WHERE status = 'pending'
        AND (
            (deadline IS NOT NULL AND date(deadline) <= ?)
            OR priority IN ('urgent', 'important')
        )
        ORDER BY 
            CASE priority WHEN 'urgent' THEN 1 WHEN 'important' THEN 2 ELSE 3 END,
            deadline ASC NULLS LAST
    ''', (today,))
    
    todos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(todos)


# ============== ANALYTICS ==============

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get productivity analytics for the last N days."""
    days = int(request.args.get('days', 7))
    conn = get_db()
    cursor = conn.cursor()
    
    # Get daily stats for the period
    stats = []
    for i in range(days - 1, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM todos
            WHERE status = 'completed' AND date(completed_at) = ?
        ''', (date,))
        completed = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM todos
            WHERE date(created_at) = ?
        ''', (date,))
        created = cursor.fetchone()['count']
        
        stats.append({
            'date': date,
            'completed': completed,
            'created': created
        })
    
    # Calculate streak
    streak = 0
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        cursor.execute('''
            SELECT COUNT(*) as count FROM todos
            WHERE status = 'completed' AND date(completed_at) = ?
        ''', (date,))
        if cursor.fetchone()['count'] > 0:
            streak += 1
        else:
            break
    
    # Best day
    cursor.execute('''
        SELECT date(completed_at) as day, COUNT(*) as count
        FROM todos
        WHERE status = 'completed' AND completed_at IS NOT NULL
        GROUP BY date(completed_at)
        ORDER BY count DESC
        LIMIT 1
    ''')
    best_day = cursor.fetchone()
    
    # Category breakdown
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM todos
        WHERE status = 'completed'
        GROUP BY category
        ORDER BY count DESC
    ''')
    by_category = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'daily_stats': stats,
        'current_streak': streak,
        'best_day': dict(best_day) if best_day else None,
        'by_category': by_category
    })


# ============== HABITS ==============

@app.route('/api/habits', methods=['GET'])
def get_habits():
    """Get all habits with today's status."""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    
    cursor.execute('''
        SELECT h.*, 
               COALESCE(ht.completed, 0) as today_completed,
               (SELECT COUNT(*) FROM habit_tracking WHERE habit_id = h.id AND completed = 1) as total_completions
        FROM habits h
        LEFT JOIN habit_tracking ht ON h.id = ht.habit_id AND ht.date = ?
        ORDER BY h.created_at
    ''', (today,))
    
    habits = [dict(row) for row in cursor.fetchall()]
    
    # Calculate streak for each habit
    for habit in habits:
        streak = 0
        for i in range(30):  # Max 30 days streak check
            date = (datetime.now() - timedelta(days=i)).date().isoformat()
            cursor.execute('''
                SELECT completed FROM habit_tracking
                WHERE habit_id = ? AND date = ?
            ''', (habit['id'], date))
            result = cursor.fetchone()
            if result and result['completed']:
                streak += 1
            else:
                break
        habit['streak'] = streak
    
    conn.close()
    return jsonify(habits)


@app.route('/api/habits', methods=['POST'])
def create_habit():
    """Create a new habit."""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO habits (name, emoji, frequency, target_count, color)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data.get('name'),
        data.get('emoji', '✅'),
        data.get('frequency', 'daily'),
        data.get('target_count', 1),
        data.get('color', '#10b981')
    ))
    
    habit_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute('SELECT * FROM habits WHERE id = ?', (habit_id,))
    habit = dict(cursor.fetchone())
    conn.close()
    
    return jsonify(habit), 201


@app.route('/api/habits/<int:habit_id>', methods=['DELETE'])
def delete_habit(habit_id):
    """Delete a habit."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM habits WHERE id = ?', (habit_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/habits/<int:habit_id>/check', methods=['PUT'])
def toggle_habit(habit_id):
    """Toggle habit completion for today."""
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    
    # Check current status
    cursor.execute('''
        SELECT completed FROM habit_tracking
        WHERE habit_id = ? AND date = ?
    ''', (habit_id, today))
    result = cursor.fetchone()
    
    if result:
        new_status = 0 if result['completed'] else 1
        cursor.execute('''
            UPDATE habit_tracking SET completed = ?
            WHERE habit_id = ? AND date = ?
        ''', (new_status, habit_id, today))
    else:
        new_status = 1
        cursor.execute('''
            INSERT INTO habit_tracking (habit_id, date, completed)
            VALUES (?, ?, 1)
        ''', (habit_id, today))
    
    conn.commit()
    conn.close()
    
    return jsonify({'completed': new_status})


@app.route('/api/habits/<int:habit_id>/history', methods=['GET'])
def get_habit_history(habit_id):
    """Get habit history for the last 30 days."""
    conn = get_db()
    cursor = conn.cursor()
    
    history = []
    for i in range(29, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        cursor.execute('''
            SELECT completed FROM habit_tracking
            WHERE habit_id = ? AND date = ?
        ''', (habit_id, date))
        result = cursor.fetchone()
        history.append({
            'date': date,
            'completed': result['completed'] if result else 0
        })
    
    conn.close()
    return jsonify(history)


# ============== CALENDAR VIEW ==============

@app.route('/api/calendar', methods=['GET'])
def get_calendar():
    """Get calendar data for a month."""
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get first and last day of month
    first_day = f"{year}-{month:02d}-01"
    if month == 12:
        last_day = f"{year + 1}-01-01"
    else:
        last_day = f"{year}-{month + 1:02d}-01"
    
    # Tasks with deadlines in this month
    cursor.execute('''
        SELECT id, title, priority, deadline, status
        FROM todos
        WHERE deadline >= ? AND deadline < ?
        ORDER BY deadline
    ''', (first_day, last_day))
    
    tasks = [dict(row) for row in cursor.fetchall()]
    
    # Group by day
    by_day = {}
    for task in tasks:
        if task['deadline']:
            day = task['deadline'][:10]
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(task)
    
    conn.close()
    
    return jsonify({
        'year': year,
        'month': month,
        'tasks_by_day': by_day
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
