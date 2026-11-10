"""Modèle de données d'une offre : colonnes, statuts et règles de pertinence.

Règle R1 : une offre a UN statut (au lieu des 4 booléens is_read / is_apply /
is_refused / is_good_offer), ce qui rend les états incohérents impossibles.

    NOUVELLE ──> LUE
        │
        └──────> POSTULEE ──> ENTRETIEN ──> REFUSEE
                     └─────────────────────> REFUSEE

Règle R2 : "écartée par l'IA" n'est PAS un statut stocké. C'est un calcul fait à
l'affichage : statut NOUVELLE + score < seuil + pas réhabilitée manuellement.
Changer le seuil dans la configuration déplace donc immédiatement les offres
entre "Nouvelles offres" et "Écartées par l'IA".
"""
from enum import StrEnum

import pandas as pd


class Status(StrEnum):
    """Étape de l'offre dans le suivi. La valeur (texte) est celle stockée en base."""
    NOUVELLE = "nouvelle"
    LUE = "lue"
    POSTULEE = "postulee"
    ENTRETIEN = "entretien"
    REFUSEE = "refusee"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]


STATUS_LABELS = {
    Status.NOUVELLE: "Nouvelle",
    Status.LUE: "Lue",
    Status.POSTULEE: "Postulée",
    Status.ENTRETIEN: "Entretien",
    Status.REFUSEE: "Refusée",
}

# Statuts considérés comme "candidature en cours"
ACTIVE_APPLICATION = (Status.POSTULEE, Status.ENTRETIEN)


class Col:
    """Noms des colonnes (centralisés pour éviter les fautes de frappe)."""
    ID = "id"
    HASH = "hash"
    LINK = "link"
    PLATFORM = "platform"
    TITLE = "title"
    COMPANY = "company"
    CONTENT = "content"
    PUBLISHED_ON = "published_on"  # date de publication (vide si inconnue, règle R4)
    SCRAPED_AT = "scraped_at"      # date de récupération par le scraper
    SCORE = "score"                # 0-100, vide si l'offre n'a pas été évaluée
    AI_COMMENT = "ai_comment"
    FORCED_RELEVANT = "forced_relevant"  # 1 si réhabilitée à la main malgré un score bas
    STATUS = "status"
    STATUS_CHANGED_AT = "status_changed_at"
    APPLIED_ON = "applied_on"      # date de candidature (règle R7)
    NOTES = "notes"                # notes libres sur la candidature (règle R7)
    INTERVIEW_COUNT = "interview_count"  # nombre d'entretiens réalisés (conservé même après un refus)
    # Colonne calculée au chargement (non stockée)
    DAYS_OLD = "days_old"


PLATFORM_LABELS = {
    "wttj": "Welcome to the Jungle",
    "apec": "APEC",
    "linkedin": "LinkedIn",
    "sp": "Service Public",
    "hw": "HelloWork",
    "ft": "France Travail",
}


# --------------------------------------------------------------------------
# Règles de pertinence (calculées, jamais stockées)
# --------------------------------------------------------------------------
def is_rejected_by_ai(df: pd.DataFrame, threshold: int) -> pd.Series:
    """Masque booléen des offres jugées non pertinentes par l'IA.

    Une offre non évaluée (score vide) n'est jamais considérée comme écartée :
    on préfère l'afficher plutôt que la perdre.
    """
    low_score = df[Col.SCORE].notna() & (df[Col.SCORE] < threshold)
    return low_score & (df[Col.FORCED_RELEVANT] == 0)


def new_relevant_offers(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Offres à traiter : statut NOUVELLE et non écartées par l'IA."""
    mask = (df[Col.STATUS] == Status.NOUVELLE) & ~is_rejected_by_ai(df, threshold)
    return df[mask]


def offers_rejected_by_ai(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Offres écartées par l'IA, encore au statut NOUVELLE."""
    mask = (df[Col.STATUS] == Status.NOUVELLE) & is_rejected_by_ai(df, threshold)
    return df[mask]
