import anthropic

from src.config import ANTHROPIC_API_KEY


def get_claude_client():
    if not ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
