#!/usr/bin/env python3
"""
Alex Todo Dashboard - Backend API
Dashboard personnel avec notifications Telegram
"""

from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from src.config import DASHBOARD_ACCESS_TOKEN, DCA_APP_URL, DCA_BACKEND_URL, PORT, TIMEZONE
from src.db import get_db, init_db
from src.services.daily_content import generate_daily_content
from src.services.reminders import check_deadlines, send_daily_recap
from src.services.telegram import send_telegram_message

app = Flask(__name__, static_folder='../static')
CORS(app)

 


# Initialize database FIRST
init_db()

# Initialize scheduler
scheduler = BackgroundScheduler(timezone=TIMEZONE)
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


@app.route('/projects')
def projects():
    """Serve the projects view."""
    return send_from_directory(app.static_folder, 'projects.html')


@app.route('/archives')
def archives():
    """Serve the archives view."""
    return send_from_directory(app.static_folder, 'archives.html')


def proxy_dca(path):
    """Proxy requests to the DCA Next.js server."""
    base_url = DCA_APP_URL.rstrip('/')
    target_url = f"{base_url}/{path.lstrip('/')}"
    if request.query_string:
        target_url = f"{target_url}?{request.query_string.decode()}"

    headers = {key: value for key, value in request.headers if key.lower() != 'host'}

    try:
        resp = requests.request(
            request.method,
            target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30
        )
    except requests.RequestException as exc:
        return jsonify({'error': 'DCA server unavailable', 'detail': str(exc)}), 502

    excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
    response = Response(resp.content, resp.status_code)
    for key, value in resp.headers.items():
        if key.lower() not in excluded_headers:
            response.headers[key] = value
    return response


@app.route('/dca')
@app.route('/dca/<path:path>')
def dca(path=''):
    """Serve the DCA tool view via the DCA server."""
    return proxy_dca(path)


@app.route('/_next/<path:path>')
def dca_next(path):
    """Serve Next.js assets for the DCA app."""
    return proxy_dca(f"_next/{path}")


@app.route('/api/analyze', methods=['POST'])
def dca_analyze_proxy():
    """Proxy DCA analyze requests to the DCA server."""
    return proxy_dca('api/analyze')


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
        # Default behavior: hide archived AND completed unless specifically requested
        query += ' AND archived = 0 AND status != "completed"'

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


@app.route('/api/todos/archived', methods=['GET'])
def get_archived_todos():
    """Get archived todos."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM todos
        WHERE archived = 1
        ORDER BY completed_at DESC, updated_at DESC
    ''')
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

    status_completed = data.get('status') == 'completed'

    for field in ['title', 'description', 'category', 'priority', 'status', 'deadline', 'archived']:
        if field in data:
            if field == 'archived' and status_completed:
                continue
            updates.append(f'{field} = ?')
            params.append(data[field])

    if status_completed:
        updates.append('completed_at = ?')
        params.append(datetime.now().isoformat())
        # Automatically archive completed tasks
        updates.append('archived = ?')
        params.append(1)

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


# ============== PROJECTS ENDPOINTS ==============

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
    projects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(projects)


@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project."""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projects (name, description, github_url, comment, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data.get('name'),
        data.get('description'),
        data.get('github_url'),
        data.get('comment'),
        data.get('status', 'active')
    ))
    project_id = cursor.lastrowid
    conn.commit()
    cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
    project = dict(cursor.fetchone())
    conn.close()
    return jsonify(project), 201


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project."""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    updates = []
    params = []
    for field in ['name', 'description', 'github_url', 'comment', 'status']:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
        
    updates.append('updated_at = ?')
    params.append(datetime.now().isoformat())
    params.append(project_id)
    
    cursor.execute(f'UPDATE projects SET {", ".join(updates)} WHERE id = ?', params)
    conn.commit()
    cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
    project = dict(cursor.fetchone())
    conn.close()
    return jsonify(project)


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============== DCA PROXY ==============

@app.route('/api/dca/analyze', methods=['POST'])
def dca_analyze():
    """Proxy request to DCA backend (local DCA app)."""
    data = request.json
    try:
        dca_api_url = f"{DCA_APP_URL.rstrip('/')}/api/analyze"
        resp = requests.post(dca_api_url, json=data, timeout=30)
        return (resp.text, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        WHERE deadline >= ? AND deadline < ? AND archived = 0
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
    app.run(host='0.0.0.0', port=PORT, debug=True)
