#!/usr/bin/env python3
"""
Alex Telegram Bot - Interface intelligente pour Todo Dashboard
Utilise Claude Haiku pour parser les messages naturels
Optimisé pour minimiser les tokens/coûts
"""

import os
import json
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
import anthropic
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
DASHBOARD_API_URL = os.getenv('DASHBOARD_API_URL', 'http://localhost:5000/api')
MAX_TOKENS = int(os.getenv('MAX_TOKENS_RESPONSE', 500))

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Claude client
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Cache pour réduire les appels API
command_cache = {}

# État conversationnel pour /add intelligent (max 2 échanges)
# Structure: {chat_id: {'task': {...}, 'state': str, 'timestamp': datetime, 'message_id': int}}
pending_tasks = {}

# État conversationnel pour création d'événement calendrier
pending_events = {}

# =============================================================================
# OPTIMISATION TOKENS : Prompts système courts et précis
# =============================================================================

SYSTEM_PROMPT_PARSER = """Tu es un assistant qui parse des messages en JSON pour une todo list.
Catégories: easynode, immobilier, content, personnel, admin
Priorités: urgent, important, normal

Réponds UNIQUEMENT en JSON valide, rien d'autre."""

SYSTEM_PROMPT_CONTENT = """Tu crées du contenu pour réseaux sociaux.
EasyNode = startup IA souveraine française, infrastructure GPU, LLM locaux
Souverain AI = marque thought leadership IA souveraine

Sois concis, impactant, professionnel."""

SYSTEM_PROMPT_TASK_ASSISTANT = """Tu es un assistant de productivité expert qui aide Alexandre à créer des tâches bien structurées.

Contexte Alexandre:
- Fondateur de EasyNode (startup IA souveraine française)
- Gère plusieurs projets: tech, immobilier, contenu, admin
- A besoin de tâches claires et actionnables

Ton rôle:
1. Reformuler la tâche de manière claire et actionnable
2. Déterminer la catégorie (easynode, immobilier, content, personnel, admin)
3. Évaluer la priorité (urgent, important, normal)
4. Estimer le temps réaliste (sois précis: 30min, 1-2h, 3-4h, etc.)
5. Proposer un guide de réalisation en 3-5 étapes concrètes
6. Poser des questions SEULEMENT si vraiment nécessaire (max 2 questions)

Règles:
- Si la tâche est claire, ne pose PAS de questions
- Si la tâche est vague ou manque d'infos critiques, pose 1-2 questions ciblées
- Le guide doit être concret et actionnable
- Estime le temps de façon réaliste

Réponds UNIQUEMENT en JSON valide."""


# =============================================================================
# FONCTIONS DASHBOARD API
# =============================================================================

def api_call(method: str, endpoint: str, data: dict = None) -> dict:
    """Appel API vers le dashboard."""
    url = f"{DASHBOARD_API_URL}/{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, json=data, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, timeout=10)
        return response.json() if response.status_code < 400 else {'error': response.text}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {'error': str(e)}


def format_guide_as_description(result: dict) -> str:
    """Format AI analysis result as a description with guide."""
    parts = []
    
    # Add time estimate
    if result.get('time_estimate'):
        parts.append(f"⏱️ Temps estimé: {result['time_estimate']}")
    
    # Add guide
    if result.get('guide'):
        parts.append("\n🧭 Guide de réalisation:")
        for i, step in enumerate(result['guide'], 1):
            parts.append(f"   {i}. {step}")
    
    return '\n'.join(parts) if parts else None


def get_todos(status: str = None) -> list:
    """Récupère les tâches."""
    endpoint = f"todos?status={status}" if status else "todos"
    return api_call('GET', endpoint)


def create_todo(title: str, category: str = 'easynode', priority: str = 'normal', deadline: str = None, description: str = None, time_estimate: str = None) -> dict:
    """Crée une nouvelle tâche."""
    data = {
        'title': title,
        'category': category,
        'priority': priority,
        'deadline': deadline
    }
    if description:
        data['description'] = description
    if time_estimate:
        # Add time estimate to description if not already included
        if description and time_estimate not in description:
            data['description'] = f"⏱️ Temps estimé: {time_estimate}\n\n{description}"
    return api_call('POST', 'todos', data)


def update_todo(todo_id: int, data: dict) -> dict:
    """Met à jour une tâche."""
    return api_call('PUT', f'todos/{todo_id}', data)


def get_stats() -> dict:
    """Récupère les statistiques."""
    return api_call('GET', 'stats')


def get_roadmap() -> list:
    """Récupère la roadmap."""
    return api_call('GET', 'roadmap')


# =============================================================================
# PARSING INTELLIGENT AVEC CLAUDE (optimisé tokens)
# =============================================================================

def parse_with_claude(message: str, intent: str) -> dict:
    """
    Parse un message naturel avec Claude Haiku.
    Intent: 'add_task', 'complete_task', 'generate_content'
    """

    if intent == 'add_task':
        user_prompt = f"""Message: "{message}"

Extrais en JSON:
{{"title": "...", "category": "easynode|immobilier|content|personnel|admin", "priority": "urgent|important|normal", "deadline": null}}"""

    elif intent == 'complete_task':
        user_prompt = f"""Message: "{message}"

Extrais en JSON:
{{"task_identifier": "...", "match_type": "id|title_partial"}}"""

    elif intent == 'generate_content':
        user_prompt = f"""Sujet: "{message}"

Génère en JSON:
{{"tweet_easynode": "max 280 chars, technique, hashtags", "linkedin_souverain": "3-5 phrases, thought leadership, emojis pros"}}"""

    else:
        return {'error': 'Unknown intent'}

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT_PARSER if intent != 'generate_content' else SYSTEM_PROMPT_CONTENT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Extraire le JSON de la réponse
        text = response.content[0].text.strip()
        # Nettoyer si markdown
        if text.startswith('```'):
            text = re.sub(r'```json?\n?', '', text)
            text = text.replace('```', '')

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error: {e}")
        return {'error': 'Invalid JSON from Claude'}
    except Exception as e:
        logger.error(f"Claude API Error: {e}")
        return {'error': str(e)}


def analyze_task_with_claude(message: str) -> dict:
    """
    Analyse une tâche avec Claude pour le mode intelligent.
    Retourne: titre, catégorie, priorité, temps estimé, guide, questions éventuelles.
    """
    # Inject session context if available
    session_context = ""
    try:
        from src.agents.assistant_agent import get_session_context_summary
        session_context = get_session_context_summary()
        if session_context:
            session_context = f"\n\n{session_context}\n"
    except Exception:
        pass

    user_prompt = f"""Analyse cette demande de tâche: "{message}"{session_context}

Réponds en JSON:
{{
    "title": "titre reformulé, clair et actionnable",
    "category": "easynode|immobilier|content|personnel|admin",
    "priority": "urgent|important|normal",
    "time_estimate": "estimation réaliste (ex: 30min, 1-2h, 3-4h, 1 jour)",
    "deadline": null,
    "guide": ["étape 1 concrète", "étape 2 concrète", "étape 3 concrète"],
    "questions": [],
    "needs_clarification": false
}}

Si la tâche est vague ou manque d'infos importantes, mets needs_clarification à true et ajoute 1-2 questions ciblées dans "questions".
Sinon, laisse questions vide et needs_clarification à false."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT_TASK_ASSISTANT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = re.sub(r'```json?\n?', '', text)
            text = text.replace('```', '')

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error in analyze_task: {e}")
        return {'error': 'Invalid JSON from Claude'}
    except Exception as e:
        logger.error(f"Claude API Error in analyze_task: {e}")
        return {'error': str(e)}


def finalize_task_with_claude(original_task: dict, user_response: str) -> dict:
    """
    Finalise une tâche en intégrant les réponses de l'utilisateur.
    """
    user_prompt = f"""Tâche en cours de création:
- Titre proposé: "{original_task.get('title', '')}"
- Catégorie: {original_task.get('category', 'easynode')}
- Priorité: {original_task.get('priority', 'normal')}
- Temps estimé: {original_task.get('time_estimate', 'non défini')}

Questions posées: {original_task.get('questions', [])}

Réponse de l'utilisateur: "{user_response}"

Intègre les réponses et finalise en JSON:
{{
    "title": "titre final",
    "category": "easynode|immobilier|content|personnel|admin",
    "priority": "urgent|important|normal",
    "time_estimate": "temps final",
    "deadline": "YYYY-MM-DD ou null",
    "guide": ["étape 1", "étape 2", "étape 3"]
}}"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT_TASK_ASSISTANT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        text = response.content[0].text.strip()
        if text.startswith('```'):
            text = re.sub(r'```json?\n?', '', text)
            text = text.replace('```', '')

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error in finalize_task: {e}")
        return {'error': 'Invalid JSON from Claude'}
    except Exception as e:
        logger.error(f"Claude API Error in finalize_task: {e}")
        return {'error': str(e)}


def detect_intent(message: str) -> str:
    """
    Détecte l'intention SANS appeler Claude (économie de tokens).
    Utilise des patterns simples.
    """
    message_lower = message.lower()

    # Patterns pour briefing quotidien (priorité haute)
    briefing_patterns = [
        "qu'est-ce que je dois faire",
        "quoi faire",
        "que dois-je faire",
        "what should i do",
        "briefing",
        "ma journée",
        "mon planning",
        "mes priorités",
        "par quoi commencer"
    ]
    if any(p in message_lower for p in briefing_patterns):
        return 'daily_briefing'

    # Patterns pour checker les emails
    email_patterns = ['email', 'mail', 'mails', 'emails', 'inbox', 'messagerie']
    if any(p in message_lower for p in email_patterns):
        return 'check_emails'

    # Patterns pour créer un événement calendrier
    event_patterns = [
        'calendrier', 'agenda', 'event', 'événement', 'evenement',
        'meeting', 'rdv', 'rendez-vous', 'rendez vous', 'planifie', 'programme'
    ]
    if any(p in message_lower for p in event_patterns):
        return 'create_event'

    # Patterns pour ajouter une tâche
    add_patterns = ['ajoute', 'add', 'nouvelle', 'créer', 'crée', 'faire', 'todo', 'tâche']
    if any(p in message_lower for p in add_patterns):
        return 'add_task'

    # Patterns pour terminer une tâche
    done_patterns = ['done', 'fait', 'terminé', 'fini', 'complete', 'check', '✓', '✅']
    if any(p in message_lower for p in done_patterns):
        return 'complete_task'

    # Patterns pour générer du contenu
    content_patterns = ['content', 'tweet', 'post', 'linkedin', 'publie', 'écris']
    if any(p in message_lower for p in content_patterns):
        return 'generate_content'

    # Patterns pour lister
    list_patterns = ['list', 'liste', 'show', 'affiche']
    if any(p in message_lower for p in list_patterns):
        return 'list_tasks'

    # Patterns pour stats/résumé
    stats_patterns = ['stats', 'résumé', 'summary', 'progression', 'combien']
    if any(p in message_lower for p in stats_patterns):
        return 'show_stats'

    # Patterns pour focus/pomodoro
    focus_patterns = ['focus', 'pomodoro', 'concentre', 'timer', 'minuteur']
    if any(p in message_lower for p in focus_patterns):
        return 'focus'

    # Patterns pour review/bilan
    review_patterns = ['review', 'revue', 'bilan', 'semaine']
    if any(p in message_lower for p in review_patterns):
        return 'weekly_review'

    # Par défaut, on considère que c'est une nouvelle tâche
    return 'add_task'


# =============================================================================
# HANDLERS TELEGRAM
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    await update.message.reply_text(
        "👋 Salut Alexandre!\n\n"
        "Je suis ton assistant personnel. Voici ce que je peux faire:\n\n"
        "🌅 **Briefing quotidien:**\n"
        "`Qu'est-ce que je dois faire ?` ou `/briefing`\n\n"
        "📬 **Emails:**\n"
        "`Mes emails` ou `/emails`\n\n"
        "🗓️ **Calendrier:**\n"
        "`Planifie un meeting demain 10h` ou `/event Démo client jeudi 14h`\n\n"
        "📝 **Ajouter une tâche:**\n"
        "`ajoute finir le script urgent easynode`\n\n"
        "✅ **Terminer une tâche:**\n"
        "`fait script LLM` ou `/done 1`\n\n"
        "📋 **Voir les tâches:**\n"
        "`/list` ou `liste`\n\n"
        "🗺️ **Roadmap:**\n"
        "`/roadmap`\n\n"
        "✍️ **Générer du contenu:**\n"
        "`/content IA souveraine`\n\n"
        "💡 Écris-moi naturellement!",
        parse_mode='Markdown'
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /list - Liste les tâches en attente"""
    todos = get_todos(status='pending')

    if not todos or 'error' in todos:
        await update.message.reply_text("❌ Erreur de connexion au dashboard")
        return

    if len(todos) == 0:
        await update.message.reply_text("🎉 Aucune tâche en attente!")
        return

    # Grouper par priorité
    urgent = [t for t in todos if t['priority'] == 'urgent']
    important = [t for t in todos if t['priority'] == 'important']
    normal = [t for t in todos if t['priority'] == 'normal']

    msg = "📋 **Tâches en cours:**\n\n"

    if urgent:
        msg += "🔴 **URGENT:**\n"
        for t in urgent:
            msg += f"  • {t['title']} ({t['category']})\n"
        msg += "\n"

    if important:
        msg += "🟠 **IMPORTANT:**\n"
        for t in important:
            msg += f"  • {t['title']} ({t['category']})\n"
        msg += "\n"

    if normal:
        msg += "🟡 **NORMAL:**\n"
        for t in normal:
            msg += f"  • {t['title']} ({t['category']})\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /stats - Affiche les statistiques"""
    stats = get_stats()

    if 'error' in stats:
        await update.message.reply_text("❌ Erreur de connexion au dashboard")
        return

    msg = f"""📊 **Dashboard Stats**

📝 Total: **{stats['total']}** tâches
⏳ En attente: **{stats['pending']}**
✅ Complétées: **{stats['completed']}**
⚠️ En retard: **{stats['overdue']}**
📅 Aujourd'hui: **{stats['today_completed']}** terminées

**Progression: {stats['completion_rate']}%**
{'🟩' * int(stats['completion_rate'] / 10)}{'⬜' * (10 - int(stats['completion_rate'] / 10))}"""

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /roadmap - Affiche la roadmap"""
    items = get_roadmap()

    if not items or 'error' in items:
        await update.message.reply_text("❌ Erreur de connexion au dashboard")
        return

    if len(items) == 0:
        await update.message.reply_text("🗺️ **Roadmap vide!**\nAjoute des objectifs via le dashboard.")
        return

    # Grouper par type
    mid_term = [i for i in items if i['type'] == 'mid_term']
    long_term = [i for i in items if i['type'] == 'long_term']

    msg = "🗺️ **Roadmap:**\n\n"

    if mid_term:
        msg += "📅 **Mi-terme (3-6 mois):**\n"
        for i in mid_term:
            status = {'in_progress': '🔄', 'completed': '✅', 'not_started': '⏳'}.get(i['status'], '➖')
            target = f" (date: {i['target_date']})" if i['target_date'] else ""
            msg += f"  {status} {i['title']}{target}\n"
        msg += "\n"

    if long_term:
        msg += "🎯 **Long-terme (6+ mois):**\n"
        for i in long_term:
            status = {'in_progress': '🔄', 'completed': '✅', 'not_started': '⏳'}.get(i['status'], '➖')
            target = f" (date: {i['target_date']})" if i['target_date'] else ""
            msg += f"  {status} {i['title']}{target}\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help - Affiche toutes les commandes disponibles"""
    msg = """📚 **Commandes disponibles:**

🌅 **Briefing & Emails**
• `/briefing` - Briefing quotidien complet
• `/emails` - Résumé des emails non lus

🗓️ **Calendrier**
• `/event <détails>` - Créer un événement (langage naturel)

📝 **Gestion des tâches**
• `/add <tâche>` - Ajoute une nouvelle tâche (mode intelligent)
• `/add --force <tâche>` - Ajoute sans reformulation IA
• `/list` - Liste toutes les tâches en attente
• `/done <id ou titre>` - Marque une tâche comme terminée

📊 **Statistiques & Planning**
• `/stats` - Affiche les statistiques du dashboard
• `/roadmap` - Affiche la roadmap (mi-terme et long-terme)
• `/review` - Bilan hebdomadaire IA

🎯 **Focus**
• `/focus` - Démarre un Pomodoro 25 min sur ta priorité #1
• `/focus stop` - Arrête la session focus

✍️ **Contenu**
• `/content <sujet>` - Génère du contenu pour réseaux sociaux

🔗 **Liens**
• `/site` - Lien vers le dashboard web
• `/help` - Affiche ce message d'aide

💡 **Astuce:** Tu peux aussi m'écrire naturellement!
_Exemples: "ajoute une tâche urgente pour finir le script", "qu'est-ce que je dois faire aujourd'hui?"_"""
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /site - Affiche le lien du dashboard"""
    dashboard_url = os.getenv('DASHBOARD_PUBLIC_URL', DASHBOARD_API_URL.replace('/api', ''))
    
    msg = f"""🌐 **Dashboard Todo**

🔗 **Lien:** {dashboard_url}

📊 Accède à ton dashboard pour:
• Visualiser toutes tes tâches
• Voir les statistiques de productivité
• Gérer ta roadmap
• Consulter le contenu quotidien

💡 _Utilise /stats pour un aperçu rapide ici._"""
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /content <sujet> - Génère du contenu"""
    if not context.args:
        await update.message.reply_text("Usage: `/content <sujet>`\nEx: `/content IA souveraine data privacy`", parse_mode='Markdown')
        return

    subject = ' '.join(context.args)
    await update.message.reply_text(f"✍️ Génération de contenu sur: *{subject}*...", parse_mode='Markdown')

    result = parse_with_claude(subject, 'generate_content')

    if 'error' in result:
        await update.message.reply_text(f"❌ Erreur: {result['error']}")
        return

    msg = f"""✨ **Contenu généré:**

**🐦 Tweet EasyNode:**
{result.get('tweet_easynode', 'N/A')}

**💼 LinkedIn Souverain AI:**
{result.get('linkedin_souverain', 'N/A')}

_Copie et adapte selon tes besoins!_"""

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /add <tâche> - Ajoute une tâche

    Flags:
        --force ou -f : Ajoute la tâche telle quelle sans reformulation IA
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/add <tâche> [urgent|important] [catégorie]`\n"
            "Option: `--force` ou `-f` pour ajouter sans reformulation IA",
            parse_mode='Markdown'
        )
        return

    args = list(context.args)
    force_mode = False

    # Détecter le flag --force ou -f
    if '--force' in args:
        force_mode = True
        args.remove('--force')
    if '-f' in args:
        force_mode = True
        args.remove('-f')

    message = ' '.join(args)

    if not message:
        await update.message.reply_text("❌ Titre de tâche requis.", parse_mode='Markdown')
        return

    if force_mode:
        await process_add_task_force(update, message)
    else:
        await process_add_task(update, message)


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /done <id ou titre> - Marque comme terminée"""
    if not context.args:
        await update.message.reply_text("Usage: `/done <id ou partie du titre>`", parse_mode='Markdown')
        return

    identifier = ' '.join(context.args)
    await process_complete_task(update, identifier)


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /briefing - Briefing quotidien complet"""
    await update.message.reply_text("🔄 Génération du briefing...", parse_mode='Markdown')

    try:
        # Import dynamique pour éviter les erreurs si Gmail pas configuré
        from src.agents.assistant_agent import what_should_i_do, suggest_daily_priorities
        briefing = what_should_i_do()

        # Append AI priorities
        try:
            priorities = suggest_daily_priorities()
            if priorities.get('priorities'):
                briefing += "\n\n🤖 **Ordre suggéré par l'IA:**\n"
                for i, p in enumerate(priorities['priorities'][:5], 1):
                    briefing += f"  {i}. {p.get('title', '?')}\n"
                if priorities.get('summary'):
                    briefing += f"\n_{priorities['summary']}_"
        except Exception:
            pass

        await update.message.reply_text(briefing, parse_mode='Markdown')
    except ImportError:
        # Fallback sans assistant_agent
        await process_simple_briefing(update)
    except Exception as e:
        logger.error(f"Briefing error: {e}")
        await process_simple_briefing(update)


async def cmd_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /emails - Résumé des emails"""
    await update.message.reply_text("📬 Vérification des emails...", parse_mode='Markdown')

    try:
        from src.agents.assistant_agent import check_emails_summary
        summary = check_emails_summary()
        await update.message.reply_text(summary, parse_mode='Markdown')
    except ImportError:
        await update.message.reply_text(
            "❌ Gmail non configuré.\n\n"
            "Pour configurer:\n"
            "1. Ajoute `gmail_credentials.json`\n"
            "2. Lance `python assistant_agent.py setup-gmail`",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur: {str(e)}")


async def cmd_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /event <détails> - Crée un événement calendrier"""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/event <détails>`\nEx: `/event Démo client jeudi 14h`",
            parse_mode='Markdown',
        )
        return

    message = ' '.join(context.args)
    await process_create_event(update, message)


async def cmd_focus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /focus - Start a 25-min Pomodoro focus session."""
    args = context.args if context.args else []

    if args and args[0].lower() == 'stop':
        # Stop any running focus timer
        jobs = context.job_queue.get_jobs_by_name(f'focus_{update.effective_chat.id}')
        if jobs:
            for job in jobs:
                job.schedule_removal()
            await update.message.reply_text("⏹️ Session focus annulée.", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Aucune session focus en cours.", parse_mode='Markdown')
        return

    # Get AI priorities to pick the top task
    task_name = "tâche prioritaire"
    try:
        from src.agents.assistant_agent import suggest_daily_priorities
        priorities = suggest_daily_priorities()
        if priorities.get('priorities'):
            top = priorities['priorities'][0]
            task_name = top.get('title', task_name)
    except Exception:
        # Fallback: get first pending task
        todos = get_todos(status='pending')
        if todos and isinstance(todos, list) and len(todos) > 0:
            task_name = todos[0].get('title', task_name)

    duration = 25  # minutes

    await update.message.reply_text(
        f"🎯 **Session Focus démarrée!**\n\n"
        f"📝 Tâche: **{task_name}**\n"
        f"⏱️ Durée: {duration} minutes\n\n"
        f"_Concentre-toi, je te notifie à la fin!_\n"
        f"💡 `/focus stop` pour annuler",
        parse_mode='Markdown'
    )

    # Schedule notification
    async def focus_end(context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"🔔 **Fin de session Focus!**\n\n"
                 f"📝 Tâche: **{task_name}**\n"
                 f"⏱️ {duration} minutes écoulées\n\n"
                 f"☕ Prends une pause de 5 min!\n"
                 f"_Utilise `/done {task_name[:20]}` si tu as terminé._",
            parse_mode='Markdown'
        )

    context.job_queue.run_once(
        focus_end,
        when=duration * 60,
        chat_id=update.effective_chat.id,
        name=f'focus_{update.effective_chat.id}'
    )


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /review - Weekly review."""
    await update.message.reply_text("📊 Génération du bilan hebdomadaire...", parse_mode='Markdown')

    try:
        from src.agents.assistant_agent import generate_weekly_review
        result = generate_weekly_review()
        review = result.get('review', 'Bilan non disponible.')
        stats = result.get('stats', {})

        msg = f"📊 **Bilan Hebdomadaire**\n\n{review}\n\n"
        if stats:
            msg += f"📈 Complétées: {stats.get('completed', 0)} | Créées: {stats.get('created', 0)}"
            if stats.get('overdue', 0) > 0:
                msg += f" | ⚠️ En retard: {stats['overdue']}"

        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Review error: {e}")
        await update.message.reply_text(f"❌ Erreur: {str(e)}")


async def process_simple_briefing(update: Update):
    """Briefing simple sans Gmail (fallback)."""
    todos = get_todos(status='pending')
    stats = get_stats()

    now = datetime.now()
    day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    day_name = day_names[now.weekday()]

    msg = f"☀️ **Bonjour Alexandre!**\n\n"
    msg += f"📅 {day_name} {now.strftime('%d/%m/%Y')}\n\n"

    if todos and not isinstance(todos, dict):
        urgent = [t for t in todos if t.get('priority') == 'urgent']
        important = [t for t in todos if t.get('priority') == 'important']

        msg += "**🎯 Priorités du jour:**\n"
        for t in (urgent + important)[:3]:
            emoji = '🔴' if t.get('priority') == 'urgent' else '🟠'
            msg += f"{emoji} {t['title']}\n"

        if len(todos) > 3:
            msg += f"\n_...et {len(todos) - 3} autres tâches_\n"

    if stats and not isinstance(stats, dict) or (isinstance(stats, dict) and 'error' not in stats):
        msg += f"\n📊 {stats.get('pending', 0)} tâches en attente"
        if stats.get('overdue', 0) > 0:
            msg += f" | ⚠️ {stats['overdue']} en retard"

    msg += "\n\n💪 Bonne journée!"

    await update.message.reply_text(msg, parse_mode='Markdown')


# =============================================================================
# TRAITEMENT DES MESSAGES NATURELS
# =============================================================================

def clean_expired_pending_tasks():
    """Nettoie les tâches en attente expirées (> 5 minutes)."""
    now = datetime.now()
    expired = [
        chat_id for chat_id, task in pending_tasks.items()
        if (now - task['timestamp']).total_seconds() > 300  # 5 minutes
    ]
    for chat_id in expired:
        del pending_tasks[chat_id]
        logger.info(f"Expired pending task for chat {chat_id}")

    expired_events = [
        chat_id for chat_id, event in pending_events.items()
        if (now - event['timestamp']).total_seconds() > 300
    ]
    for chat_id in expired_events:
        del pending_events[chat_id]
        logger.info(f"Expired pending event for chat {chat_id}")


async def process_smart_add_task(update: Update, message: str):
    """
    Traite l'ajout d'une tâche avec le mode intelligent.
    Échange 1: Analyse et proposition (+ questions si nécessaire)
    """
    chat_id = update.effective_chat.id
    
    # Nettoyer les tâches expirées
    clean_expired_pending_tasks()
    
    await update.message.reply_text("🤖 Analyse de ta tâche...", parse_mode='Markdown')
    
    # Analyser avec Claude
    result = analyze_task_with_claude(message)
    
    if 'error' in result:
        await update.message.reply_text(f"❌ Erreur: {result['error']}")
        return
    
    priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(result.get('priority', 'normal'), '⚪')
    
    # Construire le guide de réalisation
    guide_text = ""
    if result.get('guide'):
        guide_text = "\n🧭 **Guide de réalisation:**\n"
        for i, step in enumerate(result['guide'][:5], 1):
            guide_text += f"   {i}. {step}\n"
    
    # Vérifier si des questions sont nécessaires
    needs_questions = result.get('needs_clarification', False) and result.get('questions')
    
    if needs_questions:
        # Stocker l'état pour le prochain message
        pending_tasks[chat_id] = {
            'original_message': message,
            'proposed_task': result,
            'state': 'awaiting_response',
            'timestamp': datetime.now(),
            'message_id': update.message.message_id
        }
        
        # Message avec questions
        questions_text = "\n❓ **Questions:**\n"
        for i, q in enumerate(result['questions'][:2], 1):
            questions_text += f"   {i}. {q}\n"
        
        msg = f"""🤖 **Assistant Todo**

📝 **Tâche proposée:**
• Titre: "{result.get('title', message)}"
• Catégorie: {result.get('category', 'easynode')}
• Priorité: {priority_emoji} {result.get('priority', 'normal')}
• ⏱️ Temps estimé: {result.get('time_estimate', 'non défini')}
{guide_text}
{questions_text}
💬 Réponds aux questions, ou envoie **ok** pour valider tel quel, ou **annule** pour annuler."""
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    else:
        # Pas de questions, créer directement la tâche
        deadline = result.get('deadline')

        # Suggest deadline if none detected
        deadline_hint = ""
        if not deadline:
            try:
                from src.agents.assistant_agent import suggest_deadline
                suggestion = suggest_deadline(
                    category=result.get('category', 'easynode'),
                    title=result.get('title', message)
                )
                if suggestion.get('suggested_date'):
                    deadline = suggestion['suggested_date']
                    deadline_hint = f"\n📅 Deadline suggérée: {suggestion['suggested_date']} ({suggestion.get('suggested_days', '?')} jours)"
            except Exception:
                pass

        description = format_guide_as_description(result)
        todo = create_todo(
            title=result.get('title', message),
            category=result.get('category', 'easynode'),
            priority=result.get('priority', 'normal'),
            deadline=deadline,
            description=description,
            time_estimate=result.get('time_estimate')
        )

        if 'error' in todo:
            await update.message.reply_text(f"❌ Erreur création: {todo['error']}")
            return

        msg = f"""✅ **Tâche ajoutée!**

{priority_emoji} **{todo['title']}**
📁 {todo['category']} | ⏱️ {result.get('time_estimate', '?')}
🔢 ID: {todo['id']}{deadline_hint}
{guide_text}
💡 Bonne chance!"""

        await update.message.reply_text(msg, parse_mode='Markdown')


async def handle_pending_task_response(update: Update, message: str) -> bool:
    """
    Gère les réponses aux tâches en attente.
    Retourne True si le message a été traité, False sinon.
    """
    chat_id = update.effective_chat.id
    
    # Nettoyer les tâches expirées
    clean_expired_pending_tasks()
    
    # Vérifier s'il y a une tâche en attente
    if chat_id not in pending_tasks:
        return False
    
    pending = pending_tasks[chat_id]
    
    # Vérifier si c'est une annulation
    if message.lower().strip() in ['annule', 'annuler', 'cancel', 'non', 'stop']:
        del pending_tasks[chat_id]
        await update.message.reply_text("❌ Tâche annulée.", parse_mode='Markdown')
        return True
    
    # Vérifier si c'est une validation directe
    if message.lower().strip() in ['ok', 'oui', 'yes', 'valide', 'valider', 'go', '👍']:
        # Créer la tâche avec les valeurs proposées
        result = pending['proposed_task']
        description = format_guide_as_description(result)
        todo = create_todo(
            title=result.get('title', pending['original_message']),
            category=result.get('category', 'easynode'),
            priority=result.get('priority', 'normal'),
            deadline=result.get('deadline'),
            description=description,
            time_estimate=result.get('time_estimate')
        )
        
        del pending_tasks[chat_id]
        
        if 'error' in todo:
            await update.message.reply_text(f"❌ Erreur création: {todo['error']}")
            return True
        
        priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(todo['priority'], '⚪')
        
        guide_text = ""
        if result.get('guide'):
            guide_text = "\n🧭 **Guide:**\n"
            for i, step in enumerate(result['guide'][:5], 1):
                guide_text += f"   {i}. {step}\n"
        
        msg = f"""✅ **Tâche ajoutée!**

{priority_emoji} **{todo['title']}**
📁 {todo['category']} | ⏱️ {result.get('time_estimate', '?')}
🔢 ID: {todo['id']}
{guide_text}
💡 Bonne chance!"""
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return True
    
    # Sinon, traiter comme réponse aux questions
    await update.message.reply_text("🤖 Finalisation de la tâche...", parse_mode='Markdown')
    
    # Finaliser avec Claude
    final_result = finalize_task_with_claude(pending['proposed_task'], message)
    
    del pending_tasks[chat_id]
    
    if 'error' in final_result:
        await update.message.reply_text(f"❌ Erreur: {final_result['error']}")
        return True
    
    # Créer la tâche finale
    description = format_guide_as_description(final_result)
    todo = create_todo(
        title=final_result.get('title', pending['proposed_task'].get('title', '')),
        category=final_result.get('category', 'easynode'),
        priority=final_result.get('priority', 'normal'),
        deadline=final_result.get('deadline'),
        description=description,
        time_estimate=final_result.get('time_estimate')
    )
    
    if 'error' in todo:
        await update.message.reply_text(f"❌ Erreur création: {todo['error']}")
        return True
    
    priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(todo['priority'], '⚪')
    
    guide_text = ""
    if final_result.get('guide'):
        guide_text = "\n🧭 **Guide:**\n"
        for i, step in enumerate(final_result['guide'][:5], 1):
            guide_text += f"   {i}. {step}\n"
    
    deadline_text = ""
    if todo.get('deadline'):
        deadline_text = f" | 📅 {todo['deadline']}"
    
    msg = f"""✅ **Tâche ajoutée!**

{priority_emoji} **{todo['title']}**
📁 {todo['category']} | ⏱️ {final_result.get('time_estimate', '?')}{deadline_text}
🔢 ID: {todo['id']}
{guide_text}
💡 Bonne chance!"""
    
    await update.message.reply_text(msg, parse_mode='Markdown')
    return True


async def process_create_event(update: Update, message: str):
    """Crée un événement calendrier à partir d'un message naturel."""
    chat_id = update.effective_chat.id
    clean_expired_pending_tasks()

    await update.message.reply_text("🗓️ Analyse de l'événement...", parse_mode='Markdown')

    try:
        from src.agents.assistant_agent import parse_calendar_request, create_calendar_event
    except Exception as e:
        await update.message.reply_text(f"❌ Calendrier indisponible: {e}")
        return

    parsed = parse_calendar_request(message)
    if parsed.get('error'):
        await update.message.reply_text(f"❌ Erreur: {parsed['error']}")
        return

    if parsed.get('needs_clarification'):
        pending_events[chat_id] = {
            'original_message': message,
            'parsed_event': parsed,
            'state': 'awaiting_response',
            'timestamp': datetime.now(),
            'message_id': update.message.message_id,
        }

        questions = parsed.get('questions') or []
        questions_text = "\n".join([f"   {i + 1}. {q}" for i, q in enumerate(questions[:2])])
        msg = (
            "🗓️ **Besoin de précisions**\n\n"
            f"{questions_text}\n\n"
            "💬 Réponds avec les détails pour finaliser l'événement."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if not parsed.get('start_time'):
        await update.message.reply_text("❌ Impossible de déterminer la date/heure. Reformule avec une date précise.")
        return

    event = create_calendar_event(
        summary=parsed.get('summary', 'Nouvel événement'),
        start_time=parsed.get('start_time'),
        end_time=parsed.get('end_time'),
        recurrence=parsed.get('recurrence'),
    )

    if event.get('error'):
        await update.message.reply_text(f"❌ Erreur calendrier: {event['error']}")
        return

    link = event.get('htmlLink')
    recap = (
        "✅ **Événement créé**\n\n"
        f"🗓️ {event.get('summary', parsed.get('summary', 'Événement'))}\n"
        f"📅 {parsed.get('start_time')}\n"
    )
    if parsed.get('recurrence'):
        recap += f"🔁 {parsed.get('recurrence')}\n"
    if link:
        recap += f"\n🔗 {link}"

    await update.message.reply_text(recap, parse_mode='Markdown')


async def handle_pending_event_response(update: Update, message: str) -> bool:
    """Gère les réponses pour création d'événements en attente."""
    chat_id = update.effective_chat.id
    clean_expired_pending_tasks()

    if chat_id not in pending_events:
        return False

    pending = pending_events[chat_id]

    if message.lower().strip() in ['annule', 'annuler', 'cancel', 'non', 'stop']:
        del pending_events[chat_id]
        await update.message.reply_text("❌ Création d'événement annulée.", parse_mode='Markdown')
        return True

    await update.message.reply_text("🗓️ Finalisation de l'événement...", parse_mode='Markdown')

    try:
        from src.agents.assistant_agent import finalize_calendar_request, create_calendar_event
    except Exception as e:
        del pending_events[chat_id]
        await update.message.reply_text(f"❌ Calendrier indisponible: {e}")
        return True

    final_parsed = finalize_calendar_request(pending['parsed_event'], message)
    del pending_events[chat_id]

    if final_parsed.get('error'):
        await update.message.reply_text(f"❌ Erreur: {final_parsed['error']}")
        return True

    if final_parsed.get('needs_clarification'):
        await update.message.reply_text("❌ Toujours ambigu. Essaie de reformuler avec date + heure.")
        return True

    if not final_parsed.get('start_time'):
        await update.message.reply_text("❌ Impossible de déterminer la date/heure. Reformule avec une date précise.")
        return True

    event = create_calendar_event(
        summary=final_parsed.get('summary', 'Nouvel événement'),
        start_time=final_parsed.get('start_time'),
        end_time=final_parsed.get('end_time'),
        recurrence=final_parsed.get('recurrence'),
    )

    if event.get('error'):
        await update.message.reply_text(f"❌ Erreur calendrier: {event['error']}")
        return True

    link = event.get('htmlLink')
    recap = (
        "✅ **Événement créé**\n\n"
        f"🗓️ {event.get('summary', final_parsed.get('summary', 'Événement'))}\n"
        f"📅 {final_parsed.get('start_time')}\n"
    )
    if final_parsed.get('recurrence'):
        recap += f"🔁 {final_parsed.get('recurrence')}\n"
    if link:
        recap += f"\n🔗 {link}"

    await update.message.reply_text(recap, parse_mode='Markdown')
    return True


async def process_add_task(update: Update, message: str):
    """Alias pour le nouveau mode intelligent."""
    await process_smart_add_task(update, message)


async def process_add_task_force(update: Update, message: str):
    """
    Ajoute une tâche directement sans reformulation IA.
    Détecte uniquement priorité et catégorie via patterns simples.
    """
    message_lower = message.lower()

    # Détection priorité (patterns simples)
    priority = 'normal'
    if 'urgent' in message_lower:
        priority = 'urgent'
        message = re.sub(r'\s*urgent\s*', ' ', message, flags=re.IGNORECASE).strip()
    elif 'important' in message_lower:
        priority = 'important'
        message = re.sub(r'\s*important\s*', ' ', message, flags=re.IGNORECASE).strip()

    # Détection catégorie (patterns simples)
    categories = ['easynode', 'immobilier', 'content', 'personnel', 'admin']
    category = 'easynode'  # default
    for cat in categories:
        if cat in message_lower:
            category = cat
            message = re.sub(rf'\s*{cat}\s*', ' ', message, flags=re.IGNORECASE).strip()
            break

    # Nettoyer le titre
    title = ' '.join(message.split())  # Remove extra spaces

    if not title:
        await update.message.reply_text("❌ Titre de tâche requis.", parse_mode='Markdown')
        return

    # Créer la tâche directement
    todo = create_todo(
        title=title,
        category=category,
        priority=priority
    )

    if 'error' in todo:
        await update.message.reply_text(f"❌ Erreur création: {todo['error']}")
        return

    priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(priority, '⚪')

    msg = f"""✅ **Tâche ajoutée (mode direct)**

{priority_emoji} **{todo['title']}**
📁 {todo['category']}
🔢 ID: {todo['id']}"""

    await update.message.reply_text(msg, parse_mode='Markdown')


async def process_complete_task(update: Update, identifier: str):
    """Traite la complétion d'une tâche."""
    todos = get_todos(status='pending')

    if not todos:
        await update.message.reply_text("❌ Aucune tâche en attente")
        return

    # Chercher par ID
    if identifier.isdigit():
        todo_id = int(identifier)
        matching = [t for t in todos if t['id'] == todo_id]
    else:
        # Chercher par titre (partiel)
        identifier_lower = identifier.lower()
        matching = [t for t in todos if identifier_lower in t['title'].lower()]

    if not matching:
        await update.message.reply_text(f"❌ Aucune tâche trouvée pour: *{identifier}*", parse_mode='Markdown')
        return

    if len(matching) > 1:
        msg = "⚠️ Plusieurs tâches correspondent:\n"
        for t in matching:
            msg += f"  • ID {t['id']}: {t['title']}\n"
        msg += "\nPrécise l'ID: `/done <id>`"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    # Marquer comme terminée
    todo = matching[0]
    result = update_todo(todo['id'], {'status': 'completed'})

    if 'error' in result:
        await update.message.reply_text(f"❌ Erreur: {result['error']}")
        return

    await update.message.reply_text(
        f"✅ Tâche terminée!\n\n"
        f"~~{todo['title']}~~\n\n"
        f"🎉 Bravo Alexandre!",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pour les messages naturels (sans commande)."""
    message = update.message.text

    # Sécurité: ignorer si pas le bon chat
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        logger.warning(f"Message from unauthorized chat: {update.effective_chat.id}")
        return

    # PRIORITÉ: Vérifier s'il y a une tâche en attente de réponse
    if await handle_pending_event_response(update, message):
        return

    if await handle_pending_task_response(update, message):
        return  # Message traité comme réponse à une tâche en attente

    # Détecter l'intention (SANS Claude = 0 tokens)
    intent = detect_intent(message)

    if intent == 'daily_briefing':
        await cmd_briefing(update, context)

    elif intent == 'check_emails':
        await cmd_emails(update, context)

    elif intent == 'add_task':
        await process_add_task(update, message)

    elif intent == 'create_event':
        await process_create_event(update, message)

    elif intent == 'complete_task':
        # Extraire l'identifiant
        for pattern in ['fait ', 'done ', 'terminé ', 'fini ', '✅ ']:
            if pattern in message.lower():
                identifier = message.lower().split(pattern, 1)[1].strip()
                await process_complete_task(update, identifier)
                return
        await process_complete_task(update, message)

    elif intent == 'generate_content':
        # Extraire le sujet
        for pattern in ['content ', 'tweet ', 'post ', 'linkedin ']:
            if pattern in message.lower():
                subject = message.lower().split(pattern, 1)[1].strip()
                context.args = subject.split()
                await cmd_content(update, context)
                return
        await update.message.reply_text("Usage: `content <sujet>`", parse_mode='Markdown')

    elif intent == 'list_tasks':
        await cmd_list(update, context)

    elif intent == 'show_stats':
        await cmd_stats(update, context)

    elif intent == 'focus':
        await cmd_focus(update, context)

    elif intent == 'weekly_review':
        await cmd_review(update, context)

    else:
        # Par défaut, traiter comme nouvelle tâche
        await process_add_task(update, message)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Démarre le bot."""
    logger.info(f"Starting bot with model: {CLAUDE_MODEL}")

    # Créer l'application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Ajouter les handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("emails", cmd_emails))
    app.add_handler(CommandHandler("event", cmd_event))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("roadmap", cmd_roadmap))
    app.add_handler(CommandHandler("content", cmd_content))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("site", cmd_site))
    app.add_handler(CommandHandler("focus", cmd_focus))
    app.add_handler(CommandHandler("review", cmd_review))

    # Handler pour messages naturels
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Démarrer - drop_pending_updates évite les conflits avec d'anciennes connexions
    logger.info("Bot started! Listening for messages...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Ignore les updates en attente au démarrage
        poll_interval=1.0,  # Intervalle entre les requêtes (évite les conflits)
    )


if __name__ == '__main__':
    main()
