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

# Gmail scopes (read-only pour la sécurité)
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

        return {
            'todos': todos,
            'stats': stats
        }
    except Exception as e:
        return {'error': str(e), 'todos': [], 'stats': {}}


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

    # 2. Préparer le contexte (compact pour économiser les tokens)
    context_parts = []

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

    # 3. Générer le briefing avec Claude (optimisé tokens)
    context = "\n\n".join(context_parts)

    now = datetime.now()
    day_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][now.weekday()]

    prompt = f"""Date: {day_name} {now.strftime('%d/%m/%Y %H:%M')}
User: Alexandre, CPO EasyNode (IA souveraine)

{context}

Génère un briefing matinal en 5-8 lignes:
1. Salutation + météo productivité (basée sur charge)
2. Top 3 priorités du jour
3. Emails nécessitant attention (si pertinent)
4. Conseil du jour

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
