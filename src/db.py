import os
import sqlite3
from contextlib import contextmanager

from src.config import DATABASE_PATH


def ensure_db_dir() -> None:
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    ensure_db_dir()

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
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN recurrence_end_date DATE')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN parent_todo_id INTEGER')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE todos ADD COLUMN archived INTEGER DEFAULT 0')
    except Exception:
        pass

    # Create projects table
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            github_url TEXT,
            comment TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()
