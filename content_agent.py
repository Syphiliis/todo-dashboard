#!/usr/bin/env python3
"""
Agent Content Creator - Génération de contenu X + LinkedIn
Pour EasyNode et Souverain AI
Optimisé tokens avec Claude Haiku
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# =============================================================================
# CONTEXTE DES MARQUES (stocké localement = 0 tokens à chaque appel)
# =============================================================================

BRAND_CONTEXT = {
    "easynode": {
        "name": "EasyNode",
        "description": "Startup française d'IA souveraine - Infrastructure GPU, déploiement LLM locaux",
        "tone": "Technique mais accessible, innovant, français et fier",
        "audience": "CTOs, DevOps, Tech leads, startups tech françaises",
        "hashtags": ["#IA", "#AIsouveraine", "#GPU", "#LLM", "#FrenchTech", "#Cloud", "#Infrastructure"],
        "platform": "X/Twitter",
        "max_length": 280,
        "style": "Court, punchy, technique, emojis modérés"
    },
    "souverain_ai": {
        "name": "Souverain AI",
        "description": "Thought leadership sur l'IA souveraine en France et Europe",
        "tone": "Expert, visionnaire, engagé, professionnel",
        "audience": "Dirigeants, décideurs, DSI, politiques tech",
        "hashtags": ["#IAsouveraine", "#Souveraineténumérique", "#Europe", "#Tech", "#Innovation", "#DataPrivacy"],
        "platform": "LinkedIn",
        "max_length": 1300,
        "style": "Structuré, insights, storytelling pro, emojis business"
    }
}


# =============================================================================
# TEMPLATES DE CONTENU (réduit les tokens car structure pré-définie)
# =============================================================================

CONTENT_TEMPLATES = {
    "announcement": {
        "twitter": "🚀 {hook}\n\n{detail}\n\n{cta}\n\n{hashtags}",
        "linkedin": "🎯 {hook}\n\n{context}\n\n{points}\n\n{cta}\n\n{hashtags}"
    },
    "insight": {
        "twitter": "💡 {insight}\n\n{why}\n\n{hashtags}",
        "linkedin": "💡 {title}\n\n{insight}\n\n{analysis}\n\n{takeaway}\n\n{hashtags}"
    },
    "news_react": {
        "twitter": "📰 {news}\n\n{take}\n\n{hashtags}",
        "linkedin": "📰 {news}\n\n{context}\n\n{analysis}\n\n{opinion}\n\n{hashtags}"
    },
    "tutorial_tip": {
        "twitter": "⚡ Tip: {tip}\n\n{how}\n\n{hashtags}",
        "linkedin": "💼 {title}\n\n{problem}\n\n{solution}\n\n{steps}\n\n{result}\n\n{hashtags}"
    }
}


# =============================================================================
# GÉNÉRATION DE CONTENU
# =============================================================================

def generate_content(subject: str, content_type: str = "insight", brands: list = None) -> dict:
    """
    Génère du contenu pour les marques spécifiées.

    Args:
        subject: Le sujet du contenu
        content_type: announcement, insight, news_react, tutorial_tip
        brands: Liste des marques ['easynode', 'souverain_ai'] ou None pour les deux

    Returns:
        Dict avec le contenu pour chaque marque
    """
    if brands is None:
        brands = ['easynode', 'souverain_ai']

    results = {}

    for brand_key in brands:
        brand = BRAND_CONTEXT.get(brand_key)
        if not brand:
            continue

        # Prompt optimisé (court et précis)
        prompt = f"""Sujet: {subject}
Type: {content_type}
Marque: {brand['name']}
Plateforme: {brand['platform']}
Max: {brand['max_length']} caractères
Ton: {brand['tone']}
Audience: {brand['audience']}

Génère le contenu. Inclus 2-3 hashtags de: {', '.join(brand['hashtags'][:5])}

Réponds UNIQUEMENT avec le texte du post, rien d'autre."""

        try:
            response = claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=400,
                system=f"Tu es un expert en création de contenu {brand['platform']}. Style: {brand['style']}. Sois direct et impactant.",
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            # Vérifier la longueur
            if len(content) > brand['max_length']:
                content = content[:brand['max_length'] - 3] + "..."

            results[brand_key] = {
                "content": content,
                "platform": brand['platform'],
                "char_count": len(content),
                "brand": brand['name']
            }

        except Exception as e:
            results[brand_key] = {"error": str(e)}

    return results


def generate_thread(subject: str, num_tweets: int = 5) -> list:
    """
    Génère un thread Twitter pour EasyNode.

    Args:
        subject: Le sujet du thread
        num_tweets: Nombre de tweets (max 10)

    Returns:
        Liste de tweets formatés
    """
    num_tweets = min(num_tweets, 10)

    prompt = f"""Sujet: {subject}

Génère un thread Twitter de {num_tweets} tweets pour EasyNode (IA souveraine française).

Format JSON:
{{"tweets": ["tweet1", "tweet2", ...]}}

Règles:
- Tweet 1 = hook accrocheur avec emoji
- Tweets 2-{num_tweets-1} = contenu valeur
- Dernier tweet = CTA + hashtags
- Max 280 chars chacun
- Numérote: 1/{num_tweets}, 2/{num_tweets}..."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system="Tu crées des threads Twitter techniques et engageants. JSON uniquement.",
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        # Nettoyer markdown
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]

        data = json.loads(text)
        return data.get('tweets', [])

    except Exception as e:
        return [{"error": str(e)}]


def generate_linkedin_article(subject: str, word_count: int = 300) -> dict:
    """
    Génère un article LinkedIn long format pour Souverain AI.

    Args:
        subject: Le sujet de l'article
        word_count: Nombre de mots cible

    Returns:
        Dict avec titre et contenu
    """
    prompt = f"""Sujet: {subject}

Génère un article LinkedIn (~{word_count} mots) pour "Souverain AI" (thought leadership IA souveraine).

Format JSON:
{{"title": "...", "hook": "accroche 2 lignes", "body": "contenu principal", "cta": "call to action"}}

Style: Expert, insights, données si pertinent, vision Europe/France."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            system="Tu es un expert en IA souveraine et souveraineté numérique. Articles LinkedIn professionnels.",
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]

        return json.loads(text)

    except Exception as e:
        return {"error": str(e)}


def suggest_content_calendar(days: int = 7) -> list:
    """
    Suggère un calendrier de contenu pour la semaine.

    Args:
        days: Nombre de jours

    Returns:
        Liste de suggestions par jour
    """
    prompt = f"""Génère un calendrier de contenu sur {days} jours pour:
- EasyNode (Twitter): tech IA, infrastructure, actualités
- Souverain AI (LinkedIn): thought leadership, analyses

Format JSON:
{{"calendar": [
    {{"day": 1, "easynode": "sujet tweet", "souverain": "sujet linkedin"}},
    ...
]}}

Varie les formats: tips, news, insights, annonces."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            system="Tu planifies du contenu tech B2B. Suggestions concrètes et variées.",
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]

        data = json.loads(text)
        return data.get('calendar', [])

    except Exception as e:
        return [{"error": str(e)}]


# =============================================================================
# USAGE TRACKING (pour optimiser les coûts)
# =============================================================================

class UsageTracker:
    """Track API usage pour monitoring des coûts."""

    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def log(self, input_tokens: int, output_tokens: int, model: str):
        self.calls.append({
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input": input_tokens,
            "output": output_tokens
        })
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_estimated_cost(self) -> float:
        """Estime le coût en USD (prix Haiku)."""
        # Haiku pricing: $0.25/M input, $1.25/M output
        input_cost = (self.total_input_tokens / 1_000_000) * 0.25
        output_cost = (self.total_output_tokens / 1_000_000) * 1.25
        return round(input_cost + output_cost, 4)

    def summary(self) -> dict:
        return {
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": self.get_estimated_cost()
        }


# Instance globale
usage_tracker = UsageTracker()


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("""
Usage:
    python content_agent.py generate "sujet"
    python content_agent.py thread "sujet" [num_tweets]
    python content_agent.py article "sujet" [word_count]
    python content_agent.py calendar [days]
        """)
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate" and len(sys.argv) >= 3:
        subject = ' '.join(sys.argv[2:])
        result = generate_content(subject)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "thread" and len(sys.argv) >= 3:
        subject = sys.argv[2]
        num = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        result = generate_thread(subject, num)
        for i, tweet in enumerate(result, 1):
            print(f"\n--- Tweet {i} ---\n{tweet}")

    elif command == "article" and len(sys.argv) >= 3:
        subject = ' '.join(sys.argv[2:])
        result = generate_linkedin_article(subject)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "calendar":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        result = suggest_content_calendar(days)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print("Commande non reconnue")
