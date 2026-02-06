"""
AI Cache Service - SQLite-based cache for Claude API responses.
Reduces API costs by caching results with configurable TTL.
"""

import json
from datetime import datetime, timedelta

from src.db import get_db


def get_cached(cache_key: str) -> dict | None:
    """Get a cached result by key. Returns None if expired or not found."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT result_json, created_at FROM ai_cache
        WHERE cache_key = ? AND expires_at > ?
    ''', (cache_key, datetime.now().isoformat()))
    row = cursor.fetchone()
    conn.close()

    if row:
        result = json.loads(row['result_json'])
        result['_cached'] = True
        result['_cached_at'] = row['created_at']
        return result
    return None


def set_cached(cache_key: str, cache_type: str, result: dict, ttl_hours: float, todo_id: int = None) -> None:
    """Store a result in cache with TTL."""
    conn = get_db()
    cursor = conn.cursor()
    expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    result_json = json.dumps(result, ensure_ascii=False)

    cursor.execute('''
        INSERT INTO ai_cache (cache_key, cache_type, result_json, todo_id, expires_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            result_json = excluded.result_json,
            todo_id = excluded.todo_id,
            expires_at = excluded.expires_at,
            created_at = CURRENT_TIMESTAMP
    ''', (cache_key, cache_type, result_json, todo_id, expires_at))
    conn.commit()
    conn.close()


def invalidate(cache_key: str) -> None:
    """Delete a specific cache entry."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ai_cache WHERE cache_key = ?', (cache_key,))
    conn.commit()
    conn.close()


def invalidate_pattern(prefix: str) -> None:
    """Invalidate all cache entries matching a key prefix."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ai_cache WHERE cache_key LIKE ?', (prefix + '%',))
    conn.commit()
    conn.close()


def cleanup_expired() -> int:
    """Remove all expired cache entries. Returns count of deleted rows."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ai_cache WHERE expires_at <= ?', (datetime.now().isoformat(),))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def append_to_cache(cache_key: str, cache_type: str, event: dict, ttl_hours: float, max_items: int = 20) -> None:
    """Append an event to a list-type cache entry (e.g. session context)."""
    existing = get_cached(cache_key)
    if existing:
        existing.pop('_cached', None)
        existing.pop('_cached_at', None)
        events = existing.get('events', [])
    else:
        events = []

    events.append({
        'timestamp': datetime.now().isoformat(),
        **event
    })

    # Keep only the most recent items
    if len(events) > max_items:
        events = events[-max_items:]

    set_cached(cache_key, cache_type, {'events': events}, ttl_hours)
