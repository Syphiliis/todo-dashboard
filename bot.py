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


def get_todos(status: str = None) -> list:
    """Récupère les tâches."""
    endpoint = f"todos?status={status}" if status else "todos"
    return api_call('GET', endpoint)


def create_todo(title: str, category: str = 'easynode', priority: str = 'normal', deadline: str = None) -> dict:
    """Crée une nouvelle tâche."""
    return api_call('POST', 'todos', {
        'title': title,
        'category': category,
        'priority': priority,
        'deadline': deadline
    })


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
    """Handler /add <tâche> - Ajoute une tâche"""
    if not context.args:
        await update.message.reply_text("Usage: `/add <tâche> [urgent|important] [catégorie]`", parse_mode='Markdown')
        return

    message = ' '.join(context.args)
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
        from assistant_agent import what_should_i_do
        briefing = what_should_i_do()
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
        from assistant_agent import check_emails_summary
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

async def process_add_task(update: Update, message: str):
    """Traite l'ajout d'une tâche."""
    result = parse_with_claude(message, 'add_task')

    if 'error' in result:
        await update.message.reply_text(f"❌ Erreur parsing: {result['error']}")
        return

    # Créer la tâche
    todo = create_todo(
        title=result.get('title', message),
        category=result.get('category', 'easynode'),
        priority=result.get('priority', 'normal'),
        deadline=result.get('deadline')
    )

    if 'error' in todo:
        await update.message.reply_text(f"❌ Erreur création: {todo['error']}")
        return

    priority_emoji = {'urgent': '🔴', 'important': '🟠', 'normal': '🟡'}.get(todo['priority'], '⚪')

    await update.message.reply_text(
        f"✅ Tâche ajoutée!\n\n"
        f"{priority_emoji} **{todo['title']}**\n"
        f"📁 {todo['category']}\n"
        f"🔢 ID: {todo['id']}",
        parse_mode='Markdown'
    )


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

    # Détecter l'intention (SANS Claude = 0 tokens)
    intent = detect_intent(message)

    if intent == 'daily_briefing':
        await cmd_briefing(update, context)

    elif intent == 'check_emails':
        await cmd_emails(update, context)

    elif intent == 'add_task':
        await process_add_task(update, message)

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
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("roadmap", cmd_roadmap))
    app.add_handler(CommandHandler("content", cmd_content))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("done", cmd_done))

    # Handler pour messages naturels
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Démarrer
    logger.info("Bot started! Listening for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
