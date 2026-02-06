#!/usr/bin/env python3
"""
Alex Assistant Agent - Agent principal qui agrège toutes les sources
Répond à "Qu'est-ce que je dois faire ?" en checkant:
- Todo Dashboard
- Gmail (emails importants)
- Calendrier (si disponible)

Optimisé tokens avec Claude Haiku
"""

import os
import json
import pickle
import base64
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
import anthropic
import requests

# Gmail API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
DASHBOARD_API_URL = os.getenv('DASHBOARD_API_URL', 'http://localhost:5000/api')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Paris')

# Google Scopes
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.events'
]

# Claude client
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# =============================================================================
# GMAIL INTEGRATION
# =============================================================================

def get_gmail_credentials():
    """
    Récupère ou génère les credentials Gmail.
    Nécessite gmail_credentials.json (OAuth client) au premier lancement.
    """
    creds = None
    token_path = 'token.pickle'
    credentials_path = 'gmail_credentials.json'

    # Charger le token existant
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # Si pas de creds valides, authentification
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                return None  # Pas de credentials configurés

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        # Sauvegarder le token pour la prochaine fois
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def get_gmail_service():
    """Retourne le service Gmail API."""
    creds = get_gmail_credentials()
    if not creds:
        return None
    return build('gmail', 'v1', credentials=creds)


def get_calendar_service():
    """Retourne le service Google Calendar API."""
    creds = get_gmail_credentials()
    if not creds:
        return None
    return build('calendar', 'v3', credentials=creds)


def fetch_important_emails(max_results: int = 10, hours_back: int = 24) -> list:
    """
    Récupère les emails importants des dernières X heures.

    Args:
        max_results: Nombre max d'emails à récupérer
        hours_back: Heures en arrière à regarder

    Returns:
        Liste d'emails formatés
    """
    service = get_gmail_service()
    if not service:
        return [{"error": "Gmail non configuré. Ajoutez gmail_credentials.json"}]

    try:
        # Calculer la date de début
        after_date = datetime.now() - timedelta(hours=hours_back)
        after_timestamp = int(after_date.timestamp())

        # Requête: emails récents, non lus ou importants
        query = f"after:{after_timestamp} (is:unread OR is:important OR is:starred)"

        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            return []

        emails = []
        for msg in messages:
            # Récupérer les détails du message
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in message['payload']['headers']}

            # Parser la date
            date_str = headers.get('Date', '')
            try:
                email_date = parsedate_to_datetime(date_str)
                date_formatted = email_date.strftime('%d/%m %H:%M')
            except:
                date_formatted = 'N/A'

            emails.append({
                'id': msg['id'],
                'from': headers.get('From', 'Unknown'),
                'subject': headers.get('Subject', 'Sans sujet'),
                'date': date_formatted,
                'snippet': message.get('snippet', '')[:100],
                'is_unread': 'UNREAD' in message.get('labelIds', []),
                'is_important': 'IMPORTANT' in message.get('labelIds', [])
            })

        return emails

    except HttpError as error:
        return [{"error": f"Erreur Gmail API: {error}"}]
    except Exception as e:
        return [{"error": f"Erreur: {str(e)}"}]


def get_email_summary(email_id: str) -> str:
    """
    Récupère et résume un email spécifique.
    """
    service = get_gmail_service()
    if not service:
        return "Gmail non configuré"

    try:
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()

        # Extraire le body
        payload = message['payload']
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        # Limiter la taille pour économiser les tokens
        return body[:1500] if body else message.get('snippet', '')

    except Exception as e:
        return f"Erreur: {str(e)}"


def _build_email_context(emails: list, max_emails: int = 8) -> str:
    """Construit un contexte compact pour le résumé IA."""
    context_lines = []
    for idx, email in enumerate(emails[:max_emails], 1):
        body_excerpt = email.get('snippet', '')
        if email.get('id') and (email.get('is_unread') or email.get('is_important')):
            body_excerpt = get_email_summary(email['id'])
        body_excerpt = (body_excerpt or '').replace('\n', ' ').strip()
        if len(body_excerpt) > 600:
            body_excerpt = body_excerpt[:600] + '...'

        context_lines.append(
            f"{idx}. From: {email.get('from', 'Unknown')}\n"
            f"   Subject: {email.get('subject', 'Sans sujet')}\n"
            f"   Date: {email.get('date', 'N/A')}\n"
            f"   Body: {body_excerpt}"
        )
    return "\n".join(context_lines)


def summarize_emails_with_claude(emails: list) -> dict:
    """Résume les emails et extrait des tâches actionnables via Claude."""
    if not claude or not emails:
        return {}

    context = _build_email_context(emails)
    prompt = f"""Emails:\n{context}\n\nRéponds en JSON:\n{{\n  \"summary\": \"résumé en 3-5 lignes\",\n  \"action_items\": [\n    {{\"title\": \"action concise\", \"due_date\": \"YYYY-MM-DD ou null\", \"priority\": \"urgent|important|normal\"}}\n  ]\n}}\n\nRègles:\n- Les actions doivent être concrètes et déduites des emails.\n- Laisse action_items vide si rien de clair.\n- Réponds uniquement en JSON valide."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system="Tu résumes des emails et identifies des actions concrètes. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()

        return json.loads(text)
    except Exception:
        return {}


# =============================================================================
# CALENDAR INTEGRATION
# =============================================================================

def fetch_calendar_events(max_results: int = 10, days_ahead: int = 7) -> list:
    """
    Récupère les événements du calendrier pour les prochains X jours.
    """
    service = get_calendar_service()
    if not service:
        return [{"error": "Calendrier non configuré."}]

    try:
        now = datetime.utcnow().isoformat() + 'Z'
        plus_days = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            timeMax=plus_days,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        formatted_events = []

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Format: 2026-01-25T20:53:10+01:00
            try:
                dt = datetime.fromisoformat(start[:19])
                start_formatted = dt.strftime('%d/%m %H:%M')
            except:
                start_formatted = start

            formatted_events.append({
                'id': event['id'],
                'summary': event.get('summary', 'Sans titre'),
                'start': start_formatted,
                'htmlLink': event.get('htmlLink')
            })

        return formatted_events

    except Exception as e:
        return [{"error": f"Erreur Calendar API: {str(e)}"}]


def create_calendar_event(summary: str, start_time: str, end_time: str = None, recurrence: str = None) -> dict:
    """
    Crée un événement sur Google Calendar.
    - recurrence: optionnel, format RRULE (ex: 'RRULE:FREQ=WEEKLY;BYDAY=MO')
    """
    service = get_calendar_service()
    if not service:
        return {"error": "Calendrier non configuré."}

    try:
        # Default end time = 1 hour after start
        if not end_time:
            dt_start = datetime.fromisoformat(start_time)
            dt_end = dt_start + timedelta(hours=1)
            end_time = dt_end.isoformat()

        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': TIMEZONE},
            'end': {'dateTime': end_time, 'timeZone': TIMEZONE},
        }

        if recurrence:
            event['recurrence'] = [recurrence]

        event = service.events().insert(calendarId='primary', body=event).execute()
        return event

    except Exception as e:
        return {"error": str(e)}


def parse_calendar_request(message: str) -> dict:
    """Parse un message naturel en spécifications d'événement."""
    if not claude:
        return {"error": "Claude non configuré"}

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    prompt = f"""Date actuelle: {now} ({TIMEZONE})\nMessage: \"{message}\"\n\nRéponds en JSON:\n{{\n  \"summary\": \"titre clair\",\n  \"start_time\": \"YYYY-MM-DDTHH:MM:SS+02:00\",\n  \"end_time\": \"YYYY-MM-DDTHH:MM:SS+02:00 ou null\",\n  \"recurrence\": \"RRULE:FREQ=...\" ou null,\n  \"timezone\": \"{TIMEZONE}\",\n  \"needs_clarification\": false,\n  \"questions\": []\n}}\n\nRègles:\n- Si l'heure n'est pas donnée, propose 09:00 locale.\n- Si récurrence (ex: \"tous les lundis\"), génère une RRULE valide et utilise la prochaine occurrence comme start_time.\n- Si c'est ambigu, mets needs_clarification à true et ajoute 1-2 questions ciblées.\n- Réponds uniquement en JSON valide."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system="Tu converts des demandes d'événements calendrier en données structurées. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()

        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def finalize_calendar_request(original: dict, user_response: str) -> dict:
    """Finalise une demande d'événement après clarification."""
    if not claude:
        return {"error": "Claude non configuré"}

    prompt = f"""Demande initiale:\n{json.dumps(original, ensure_ascii=False)}\n\nRéponse utilisateur: \"{user_response}\"\n\nRends un JSON final:\n{{\n  \"summary\": \"titre clair\",\n  \"start_time\": \"YYYY-MM-DDTHH:MM:SS+02:00\",\n  \"end_time\": \"YYYY-MM-DDTHH:MM:SS+02:00 ou null\",\n  \"recurrence\": \"RRULE:FREQ=...\" ou null,\n  \"timezone\": \"{TIMEZONE}\",\n  \"needs_clarification\": false,\n  \"questions\": []\n}}\n\nRéponds uniquement en JSON valide."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system="Tu finalises des demandes d'événements calendrier. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()

        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def create_calendar_event_from_message(message: str) -> dict:
    """Crée un événement calendrier à partir d'une demande en langage naturel."""
    parsed = parse_calendar_request(message)
    if parsed.get('error') or parsed.get('needs_clarification'):
        return parsed

    return create_calendar_event(
        summary=parsed.get('summary', 'Nouvel événement'),
        start_time=parsed.get('start_time'),
        end_time=parsed.get('end_time'),
        recurrence=parsed.get('recurrence'),
    )


# =============================================================================
# DASHBOARD INTEGRATION
# =============================================================================

def fetch_dashboard_todos() -> dict:
    """
    Récupère les tâches du dashboard.
    """
    try:
        response = requests.get(f"{DASHBOARD_API_URL}/todos?status=pending", timeout=10)
        todos = response.json() if response.status_code == 200 else []

        stats_response = requests.get(f"{DASHBOARD_API_URL}/stats", timeout=10)
        stats = stats_response.json() if stats_response.status_code == 200 else {}
        
        daily_response = requests.get(f"{DASHBOARD_API_URL}/daily-content", timeout=10)
        daily_content = daily_response.json() if daily_response.status_code == 200 and 'error' not in daily_response.json() else {}

        return {
            'todos': todos,
            'stats': stats,
            'daily_content': daily_content
        }
    except Exception as e:
        return {'error': str(e), 'todos': [], 'stats': {}, 'daily_content': {}}


# =============================================================================
# AGENT PRINCIPAL
# =============================================================================

def generate_daily_briefing() -> str:
    """
    Génère le briefing quotidien en agrégeant toutes les sources.
    Répond à "Qu'est-ce que je dois faire ?"
    """

    # 1. Récupérer les données
    dashboard_data = fetch_dashboard_todos()
    emails = fetch_important_emails(max_results=10, hours_back=24)
    calendar_events = fetch_calendar_events(max_results=10, days_ahead=2)

    # 2. Préparer le contexte (compact pour économiser les tokens)
    context_parts = []

    # Daily Content (Citation/Fait)
    daily_content = dashboard_data.get('daily_content', {})
    if daily_content:
        quote = daily_content.get('quote')
        author = daily_content.get('quote_author')
        if quote:
            context_parts.append(f"CITATION: \"{quote}\" — {author}")

    # Tâches
    todos = dashboard_data.get('todos', [])
    if todos:
        urgent = [t for t in todos if t.get('priority') == 'urgent']
        important = [t for t in todos if t.get('priority') == 'important']
        normal = [t for t in todos if t.get('priority') == 'normal']

        tasks_summary = f"TÂCHES ({len(todos)} en attente):\n"
        if urgent:
            tasks_summary += f"🔴 URGENT: {', '.join([t['title'] for t in urgent])}\n"
        if important:
            tasks_summary += f"🟠 IMPORTANT: {', '.join([t['title'] for t in important])}\n"
        if normal:
            tasks_summary += f"🟡 NORMAL: {', '.join([t['title'][:30] for t in normal[:5]])}\n"

        context_parts.append(tasks_summary)

    # Stats
    stats = dashboard_data.get('stats', {})
    if stats:
        context_parts.append(
            f"STATS: {stats.get('completed', 0)} terminées, {stats.get('pending', 0)} en attente, "
            f"{stats.get('overdue', 0)} en retard"
        )

    # Emails
    if emails and not any('error' in e for e in emails):
        unread = [e for e in emails if e.get('is_unread')]
        important_emails = [e for e in emails if e.get('is_important')]

        emails_summary = f"EMAILS ({len(emails)} récents):\n"
        if unread:
            emails_summary += f"📬 Non lus ({len(unread)}): "
            emails_summary += ', '.join([f"{e['from'].split('<')[0].strip()}: {e['subject'][:30]}" for e in unread[:5]])
            emails_summary += "\n"
        if important_emails:
            emails_summary += f"⭐ Importants: "
            emails_summary += ', '.join([e['subject'][:40] for e in important_emails[:3]])

        context_parts.append(emails_summary)
    elif emails and 'error' in emails[0]:
        context_parts.append(f"EMAILS: {emails[0]['error']}")

    # Calendar
    if calendar_events and not any('error' in e for e in calendar_events):
        cal_summary = f"CALENDRIER ({len(calendar_events)} prochains):\n"
        for e in calendar_events[:5]:
            cal_summary += f"📅 {e['start']}: {e['summary']}\n"
        context_parts.append(cal_summary)
    elif calendar_events and 'error' in calendar_events[0]:
        context_parts.append(f"CALENDRIER: {calendar_events[0]['error']}")

    # 3. Générer le briefing avec Claude (optimisé tokens)
    context = "\n\n".join(context_parts)

    now = datetime.now()
    day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][now.weekday()]

    # Inject session context
    session_ctx = get_session_context_summary()
    if session_ctx:
        context += f"\n\n{session_ctx}"

    prompt = f"""Date: {day_name} {now.strftime('%d/%m/%Y %H:%M')}
User: Alexandre, CPO EasyNode (IA souveraine)

{context}

Génère un briefing matinal en 5-8 lignes:
1. Salutation + météo productivité
2. Citation inspirante (si fournie)
3. Top priorités
4. Emails (si pertinent)
5. Conseil du jour

Sois direct, motivant, concis."""


    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system="Tu es l'assistant personnel d'Alexandre. Briefings concis, motivants, actionnables. Tutoie.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    except Exception as e:
        # Fallback sans Claude
        return generate_fallback_briefing(dashboard_data, emails)


def generate_fallback_briefing(dashboard_data: dict, emails: list) -> str:
    """
    Génère un briefing basique sans Claude (si erreur API).
    """
    now = datetime.now()
    day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][now.weekday()]

    briefing = f"📅 **{day_name} {now.strftime('%d/%m/%Y')}**\n\n"

    todos = dashboard_data.get('todos', [])
    if todos:
        urgent = [t for t in todos if t.get('priority') == 'urgent']
        important = [t for t in todos if t.get('priority') == 'important']

        briefing += "**🎯 Priorités du jour:**\n"
        for t in (urgent + important)[:3]:
            emoji = '🔴' if t.get('priority') == 'urgent' else '🟠'
            briefing += f"{emoji} {t['title']}\n"

        briefing += f"\n📊 {len(todos)} tâches en attente\n"

    if emails and not any('error' in e for e in emails):
        unread = [e for e in emails if e.get('is_unread')]
        if unread:
            briefing += f"\n📬 {len(unread)} emails non lus\n"

    briefing += "\n💪 Bonne journée Alexandre!"
    return briefing


def send_briefing_telegram(briefing: str) -> bool:
    """
    Envoie le briefing via Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": briefing,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False


# =============================================================================
# AI FEATURES WITH CACHE
# =============================================================================

def suggest_daily_priorities() -> dict:
    """Suggest optimal daily priority order for pending tasks. Cached 20h."""
    from src.services.ai_cache import get_cached, set_cached

    today = datetime.now().date().isoformat()
    cache_key = f"prioritize:{today}"

    cached = get_cached(cache_key)
    if cached:
        return cached

    # Fetch pending tasks
    try:
        response = requests.get(f"{DASHBOARD_API_URL}/todos?status=pending", timeout=10)
        todos = response.json() if response.status_code == 200 else []
    except Exception:
        return {'error': 'Cannot fetch todos'}

    if not todos:
        return {'priorities': [], 'reasoning': 'Aucune tâche en attente.'}

    # Build compact task list for prompt
    task_lines = []
    for t in todos[:20]:
        deadline = f" (deadline: {t.get('deadline', 'none')})" if t.get('deadline') else ""
        task_lines.append(f"- [{t['id']}] {t['title']} | {t['category']} | {t['priority']}{deadline}")

    now = datetime.now()
    day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][now.weekday()]

    prompt = f"""Date: {day_name} {now.strftime('%d/%m/%Y')}
Tâches en attente:
{chr(10).join(task_lines)}

Propose un ordre optimal pour la journée (max 7 tâches). Critères: urgence, deadlines proches, impact business.

Réponds en JSON:
{{"priorities": [{{"id": 1, "title": "...", "reason": "courte raison"}}], "summary": "phrase motivante"}}"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system="Tu optimises l'ordre des tâches pour la productivité. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
    except Exception:
        # Fallback: return tasks sorted by priority
        priority_order = {'urgent': 0, 'important': 1, 'normal': 2}
        sorted_todos = sorted(todos[:7], key=lambda t: priority_order.get(t.get('priority', 'normal'), 2))
        result = {
            'priorities': [{'id': t['id'], 'title': t['title'], 'reason': t['priority']} for t in sorted_todos],
            'summary': 'Ordre basé sur les priorités.'
        }

    set_cached(cache_key, 'prioritize', result, ttl_hours=20)
    return result


def suggest_deadline(category: str, title: str) -> dict:
    """Suggest a deadline based on velocity data or AI. Cached 24h."""
    from src.services.ai_cache import get_cached, set_cached
    from src.db import get_db

    today = datetime.now().date().isoformat()
    cache_key = f"velocity:{category}:{today}"

    cached = get_cached(cache_key)
    if cached:
        avg_days = cached.get('avg_days')
        if avg_days:
            suggested = datetime.now() + timedelta(days=avg_days)
            return {
                'suggested_date': suggested.date().isoformat(),
                'suggested_days': avg_days,
                'source': 'velocity'
            }

    # Calculate average completion time for this category
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG(julianday(completed_at) - julianday(created_at)) as avg_days,
               COUNT(*) as count
        FROM todos
        WHERE category = ? AND status = 'completed' AND completed_at IS NOT NULL
    ''', (category,))
    row = cursor.fetchone()
    conn.close()

    if row and row['count'] and row['count'] >= 5 and row['avg_days']:
        avg_days = round(row['avg_days'])
        if avg_days < 1:
            avg_days = 1
        set_cached(cache_key, 'velocity', {'avg_days': avg_days, 'count': row['count']}, ttl_hours=24)
        suggested = datetime.now() + timedelta(days=avg_days)
        return {
            'suggested_date': suggested.date().isoformat(),
            'suggested_days': avg_days,
            'source': 'velocity'
        }

    # Not enough data: use AI
    try:
        prompt = f'Tâche: "{title}" (catégorie: {category}). Estime le nombre de jours réaliste pour la compléter. Réponds en JSON: {{"days": N, "reason": "courte raison"}}'
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=100,
            system="Tu estimes des délais de tâches. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        days = result.get('days', 7)
    except Exception:
        days = 7

    set_cached(cache_key, 'velocity', {'avg_days': days, 'count': 0}, ttl_hours=24)
    suggested = datetime.now() + timedelta(days=days)
    return {
        'suggested_date': suggested.date().isoformat(),
        'suggested_days': days,
        'source': 'ai'
    }


def decompose_task(todo_id: int) -> dict:
    """Decompose a task into 3-6 subtasks using AI. Cached 7 days."""
    from src.services.ai_cache import get_cached, set_cached
    from src.db import get_db

    cache_key = f"decompose:{todo_id}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Fetch the task
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {'error': 'Task not found'}

    todo = dict(row)
    prompt = f"""Tâche: "{todo['title']}"
Description: {todo.get('description') or 'Aucune'}
Catégorie: {todo.get('category', 'general')}

Décompose cette tâche en 3-6 sous-tâches concrètes et actionnables.

Réponds en JSON:
{{"subtasks": [{{"title": "sous-tâche claire", "priority": "normal|important", "estimated_time": "30min|1h|2h"}}]}}"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system="Tu décomposes des tâches en sous-tâches actionnables. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
    except Exception:
        return {'error': 'AI decomposition failed'}

    result['parent_id'] = todo_id
    result['parent_title'] = todo['title']
    set_cached(cache_key, 'decompose', result, ttl_hours=168, todo_id=todo_id)
    return result


def update_session_context(event: dict) -> None:
    """Append an event to today's session context cache."""
    from src.services.ai_cache import append_to_cache

    today = datetime.now().date().isoformat()
    cache_key = f"session:{today}"
    append_to_cache(cache_key, 'session', event, ttl_hours=20, max_items=20)


def get_session_context_summary() -> str:
    """Get a 2-3 line summary of today's session context."""
    from src.services.ai_cache import get_cached

    today = datetime.now().date().isoformat()
    cache_key = f"session:{today}"
    cached = get_cached(cache_key)
    if not cached or not cached.get('events'):
        return ""

    events = cached['events']
    lines = []
    for e in events[-5:]:
        lines.append(f"- {e.get('type', '?')}: {e.get('detail', '?')}")
    return "Contexte du jour:\n" + "\n".join(lines)


def generate_weekly_review() -> dict:
    """Generate a weekly review from task_history data. Cached 7 days."""
    from src.services.ai_cache import get_cached, set_cached
    from src.db import get_db

    week_key = datetime.now().strftime('%Y-W%W')
    cache_key = f"weekly_review:{week_key}"

    cached = get_cached(cache_key)
    if cached:
        return cached

    conn = get_db()
    cursor = conn.cursor()

    # Get last 7 days of history
    cursor.execute('''
        SELECT * FROM task_history
        WHERE date >= date('now', '-7 days')
        ORDER BY date ASC
    ''')
    history = [dict(row) for row in cursor.fetchall()]

    # Category breakdown for the week
    cursor.execute('''
        SELECT category, COUNT(*) as count FROM todos
        WHERE status = 'completed' AND date(completed_at) >= date('now', '-7 days')
        GROUP BY category ORDER BY count DESC
    ''')
    by_category = [dict(row) for row in cursor.fetchall()]

    # Overdue count
    cursor.execute('''
        SELECT COUNT(*) as count FROM todos
        WHERE status = 'pending' AND deadline IS NOT NULL AND deadline < ?
    ''', (datetime.now().isoformat(),))
    overdue = cursor.fetchone()['count']

    conn.close()

    total_completed = sum(h.get('completed_count', 0) for h in history)
    total_created = sum(h.get('created_count', 0) for h in history)
    avg_pending = round(sum(h.get('pending_count', 0) for h in history) / max(len(history), 1))

    stats_text = f"""Semaine {week_key}:
- Complétées: {total_completed}
- Créées: {total_created}
- Pending moyen: {avg_pending}
- En retard: {overdue}
- Par catégorie: {', '.join(f"{c['category']}({c['count']})" for c in by_category)}"""

    try:
        prompt = f"""{stats_text}

Génère un bilan hebdomadaire concis (5-8 lignes):
1. Résumé de la semaine (productif? en retard?)
2. Points forts
3. Points d'amélioration
4. Objectif pour la semaine prochaine

Sois direct et motivant."""

        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system="Tu fais des bilans hebdomadaires de productivité. Concis et motivant. Tutoie Alexandre.",
            messages=[{"role": "user", "content": prompt}]
        )
        review_text = response.content[0].text.strip()
    except Exception:
        review_text = f"Bilan semaine {week_key}: {total_completed} tâches complétées, {total_created} créées, {overdue} en retard."

    result = {
        'review': review_text,
        'stats': {
            'completed': total_completed,
            'created': total_created,
            'avg_pending': avg_pending,
            'overdue': overdue,
            'by_category': by_category
        },
        'week': week_key,
        'generated_at': datetime.now().isoformat()
    }

    set_cached(cache_key, 'weekly_review', result, ttl_hours=168)
    return result


# =============================================================================
# COMMANDES SPÉCIFIQUES
# =============================================================================

def what_should_i_do() -> str:
    """
    Commande principale: "Qu'est-ce que je dois faire ?"
    """
    return generate_daily_briefing()


def check_emails_summary() -> str:
    """
    Résumé rapide des emails.
    """
    emails = fetch_important_emails(max_results=15, hours_back=48)

    if not emails:
        return "📭 Aucun email important dans les dernières 48h"

    if 'error' in emails[0]:
        return f"❌ {emails[0]['error']}"

    ai_summary = summarize_emails_with_claude(emails)
    if ai_summary.get('summary') or ai_summary.get('action_items'):
        summary = f"📬 **Résumé IA ({len(emails)} emails)**\n\n{ai_summary.get('summary', '').strip()}\n\n"
        actions = ai_summary.get('action_items') or []
        if actions:
            summary += "**✅ Actions proposées:**\n"
            for item in actions[:6]:
                due = f" (due {item.get('due_date')})" if item.get('due_date') else ""
                priority = item.get('priority', 'normal')
                summary += f"• [{priority}] {item.get('title')}{due}\n"
        return summary.strip()

    unread = [e for e in emails if e.get('is_unread')]
    important = [e for e in emails if e.get('is_important')]

    summary = f"📬 **Emails ({len(emails)} récents)**\n\n"

    if unread:
        summary += f"**Non lus ({len(unread)}):**\n"
        for e in unread[:5]:
            sender = e['from'].split('<')[0].strip()[:20]
            summary += f"• {sender}: {e['subject'][:40]}\n"
        summary += "\n"

    if important:
        summary += f"**Importants ({len(important)}):**\n"
        for e in important[:3]:
            summary += f"⭐ {e['subject'][:50]}\n"

    return summary


def check_overdue_tasks() -> str:
    """
    Liste les tâches en retard.
    """
    dashboard_data = fetch_dashboard_todos()
    stats = dashboard_data.get('stats', {})

    overdue_count = stats.get('overdue', 0)

    if overdue_count == 0:
        return "✅ Aucune tâche en retard! Bravo!"

    todos = dashboard_data.get('todos', [])
    # Note: Le dashboard actuel ne stocke pas de deadline
    # À améliorer si tu ajoutes les deadlines

    return f"⚠️ {overdue_count} tâche(s) en retard"


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("""
Alex Assistant Agent - CLI

Usage:
    python assistant_agent.py briefing     # Briefing complet du jour
    python assistant_agent.py emails       # Résumé emails
    python assistant_agent.py tasks        # Tâches en attente
    python assistant_agent.py send         # Envoyer briefing sur Telegram
    python assistant_agent.py setup-gmail  # Configurer Gmail (1ère fois)
        """)
        sys.exit(0)

    command = sys.argv[1]

    if command == "briefing":
        print(what_should_i_do())

    elif command == "emails":
        print(check_emails_summary())

    elif command == "tasks":
        data = fetch_dashboard_todos()
        todos = data.get('todos', [])
        if not todos:
            print("🎉 Aucune tâche en attente!")
        else:
            for t in todos:
                emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(t.get('priority'), '⚪')
                print(f"{emoji} [{t['id']}] {t['title']} ({t['category']})")

    elif command == "send":
        briefing = what_should_i_do()
        print(briefing)
        print("\n---")
        if send_briefing_telegram(briefing):
            print("✅ Briefing envoyé sur Telegram!")
        else:
            print("❌ Erreur envoi Telegram")

    elif command == "setup-gmail":
        print("🔧 Configuration Gmail...")
        print("Assurez-vous que 'gmail_credentials.json' est présent.")
        creds = get_gmail_credentials()
        if creds:
            print("✅ Gmail configuré avec succès!")
            # Test
            emails = fetch_important_emails(max_results=3)
            print(f"📬 Test: {len(emails)} emails récupérés")
        else:
            print("❌ Échec configuration. Vérifiez gmail_credentials.json")

    else:
        print(f"Commande inconnue: {command}")
