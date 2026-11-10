"""Filtres appliqués aux nouvelles offres AVANT le LLM (gratuits et instantanés).

- Filtre de langue : les offres dans une langue non autorisée ne sont pas enregistrées
  (comportement de l'ancienne version, conservé).
- Pré-filtre par mots : les offres contenant un mot de la liste noire (ou aucun mot de
  la liste blanche) sont enregistrées avec un score de 0 : elles apparaissent dans
  « Écartées par l'IA » et ne sont pas re-scrapées comme nouvelles (règle R3).
"""
from langdetect import DetectorFactory, LangDetectException, detect

from jobfinder.config import PreFilterConfig

DetectorFactory.seed = 0  # langdetect est aléatoire par défaut : on fige le résultat

PRE_FILTER_COMMENT = "Écartée par le pré-filtre"


def detect_language(text: str) -> str:
    """Code langue ("fr", "en"...) ou "autre" si la détection échoue."""
    try:
        return detect(text)
    except LangDetectException:
        return "autre"


def is_language_allowed(text: str, allowed: dict[str, bool]) -> bool:
    """allowed = {"fr": True, "en": False, "autre": False} (config.language_filter)."""
    if all(allowed.values()):  # tout est autorisé : inutile de détecter
        return True
    language = detect_language(text)
    if language not in allowed:
        language = "autre"
    return allowed.get(language, False)


def pre_filter_reason(title: str, content: str, config: PreFilterConfig) -> str | None:
    """Raison pour laquelle l'offre est écartée, ou None si elle passe le filtre."""
    if not config.enabled:
        return None
    text = f"{title} {content}".lower()

    for word in config.blacklist:
        if word.strip() and word.lower() in text:
            return f"{PRE_FILTER_COMMENT} (mot exclu : « {word} »)"

    whitelist = [w for w in config.whitelist if w.strip()]
    if whitelist and not any(word.lower() in text for word in whitelist):
        return f"{PRE_FILTER_COMMENT} (aucun mot requis trouvé)"
    return None
