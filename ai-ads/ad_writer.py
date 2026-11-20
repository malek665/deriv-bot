"""Génère des variantes de publicités Facebook/Instagram avec Claude."""

import json
import os

import anthropic

MODEL = "claude-opus-5-5"

CTA_TYPES = [
    "SHOP_NOW", "LEARN_MORE", "SIGN_UP", "ORDER_NOW", "BOOK_TRAVEL",
    "CONTACT_US", "GET_OFFER", "SUBSCRIBE", "DOWNLOAD",
]

AD_SCHEMA = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "angle": {"type": "string"},
                    "primary_text": {"type": "string"},
                    "headline": {"type": "string"},
                    "description": {"type": "string"},
                    "call_to_action": {"type": "string", "enum": CTA_TYPES},
                    "image_idea": {"type": "string"},
                },
                "required": [
                    "angle", "primary_text", "headline",
                    "description", "call_to_action", "image_idea",
                ],
                "additionalProperties": False,
            },
        },
        "targeting_tips": {"type": "string"},
    },
    "required": ["variants", "targeting_tips"],
    "additionalProperties": False,
}

SYSTEM = """Tu es un expert en publicité Facebook et Instagram pour les petits commerces.
Tu écris des publicités qui donnent envie de cliquer, dans la langue demandée.

Règles :
- Texte principal : 1 à 3 phrases courtes, une accroche forte dès les premiers mots. 125 caractères idéalement.
- Titre : 40 caractères maximum.
- Description : 30 caractères maximum.
- Chaque variante prend un angle différent (prix, bénéfice, urgence, preuve sociale, émotion...).
- Respecte les règles publicitaires de Meta : pas de promesses fausses ou exagérées,
  pas d'allusion aux caractéristiques personnelles du lecteur (« Tu es en surpoids ? »),
  pas d'avant/après trompeur. N'invente ni prix, ni promotion, ni avis client qui ne sont pas dans la description.
- image_idea : décris en une phrase le visuel à utiliser.
- targeting_tips : 2 à 3 phrases de conseils de ciblage (âge, centres d'intérêt, zone)."""


class AdWriterError(Exception):
    pass


def generate_ads(business: str, product: str, audience: str, goal: str,
                 language: str = "français", count: int = 3) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise AdWriterError("Clé API manquante : ajoutez ANTHROPIC_API_KEY=sk-ant-... dans le fichier .env, "
                            "enregistrez, puis relancez l'outil.")
    client = anthropic.Anthropic()
    prompt = (
        f"Commerce : {business}\n"
        f"Produit ou offre à promouvoir : {product}\n"
        f"Clients visés : {audience or 'non précisé'}\n"
        f"Objectif : {goal or 'attirer des clients'}\n"
        f"Langue des pubs : {language}\n\n"
        f"Écris {count} variantes de publicité."
    )
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": AD_SCHEMA},
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise AdWriterError("Clé API Anthropic invalide ou manquante (ANTHROPIC_API_KEY).") from e
    except anthropic.RateLimitError as e:
        raise AdWriterError("Trop de demandes à l'IA, réessayez dans une minute.") from e
    except anthropic.APIStatusError as e:
        raise AdWriterError(f"Erreur de l'IA ({e.status_code}) : {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AdWriterError("Impossible de joindre l'IA (connexion réseau).") from e
    except anthropic.AnthropicError as e:
        raise AdWriterError(f"Erreur de l'IA : {e}") from e

    if response.stop_reason == "refusal":
        raise AdWriterError("L'IA a refusé d'écrire cette publicité. Reformulez la description du produit.")
    if response.stop_reason == "max_tokens":
        raise AdWriterError("Réponse de l'IA coupée, demandez moins de variantes.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise AdWriterError("Réponse vide de l'IA.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AdWriterError("Réponse de l'IA illisible, réessayez.") from e
