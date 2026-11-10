"""Lecture des dates de publication affichées par les sites.

Règle R4 : une date illisible renvoie None (date inconnue) au lieu de « aujourd'hui ».
Avant, une vieille offre dont la date n'était pas comprise passait pour une offre du jour.
"""
import re
from datetime import date, timedelta

import dateparser


def parse_relative_date(text: str, today: date | None = None) -> date | None:
    """Convertit un texte relatif en date.

    Exemples : "il y a 3 heures", "Publié aujourd'hui", "hier", "il y a 5 jours",
    "Publié il y a 2 semaines", "il y a 1 mois", "plus de 30 jours".
    """
    if not text:
        return None
    today = today or date.today()
    text = text.lower()
    number = re.search(r"(\d+)", text)
    count = int(number.group(1)) if number else 1  # "il y a un mois" -> 1

    if "aujourd" in text or "heure" in text or "minute" in text or "instant" in text:
        return today
    if "hier" in text:
        return today - timedelta(days=1)
    if "jour" in text:
        return today - timedelta(days=count) if number else None
    if "semaine" in text:
        return today - timedelta(weeks=count)
    if "mois" in text:
        return today - timedelta(days=30 * count)
    return None


def parse_french_date(text: str) -> date | None:
    """Convertit une date écrite en français ("12 octobre 2026", "12/10/2026") en date."""
    if not text:
        return None
    parsed = dateparser.parse(text, languages=["fr"], settings={"DATE_ORDER": "DMY"})
    return parsed.date() if parsed else None
