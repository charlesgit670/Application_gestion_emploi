"""Détection des doublons probables entre plateformes (règle R5, version prudente).

Une même offre est souvent publiée sur plusieurs sites (LinkedIn, HelloWork, APEC...)
avec un nom d'entreprise et un titre légèrement différents :
    "Data Engineer (H / F)" chez "Servier France"   (LinkedIn)
    "Data Engineer H/F"     chez "Servier"          (HelloWork)

Deux offres sont signalées comme doublon probable si :
    - elles viennent de plateformes différentes ;
    - leur entreprise est identique une fois normalisée (accents, casse, SAS, France,
      localisation "- 92 - Ville" de France Travail... retirés) ;
    - leurs titres normalisés sont très proches (similarité >= 0,90) ;
    - elles sont publiées à moins de 3 semaines d'écart (ou date inconnue).

Rien n'est fusionné ni supprimé : l'interface affiche seulement un avertissement
(« déjà postulé sur LinkedIn », par exemple). Seuil choisi sur les données réelles :
en dessous de 0,90, des postes différents de la même entreprise sont confondus.
"""
import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd

from jobfinder.models import Col

TITLE_SIMILARITY = 0.90
MAX_DAYS_APART = 21

# Mots sans valeur pour identifier une entreprise
COMPANY_NOISE = r"\b(sas|sasu|sa|sarl|se|group|groupe|france|the)\b"
# Mentions sans valeur pour identifier un poste : (H/F), F/H, CDI...
TITLE_NOISE = r"\b(h\s*/\s*f|f\s*/\s*h|h\s*-\s*f|f\s*-\s*h|m\s*/\s*f|f\s*/\s*m|cdi)\b"


def _ascii_lower(text: str) -> str:
    """Minuscules sans accents : "Ingénieur" -> "ingenieur"."""
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()


def normalize_title(title: str) -> str:
    text = _ascii_lower(title)
    text = re.sub(r"\(.*?\)", " ", text)  # contenu entre parenthèses : (H/F), (CDI)...
    text = re.sub(TITLE_NOISE, " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize_company(company: str) -> str:
    text = " ".join(str(company).split())           # retours à la ligne de France Travail
    text = re.sub(r"\s-\s\d{2,3}\b.*$", "", text)   # "ENGIE - 92 - Courbevoie" -> "ENGIE"
    text = re.sub(r"[^a-z0-9]+", " ", _ascii_lower(text))
    return " ".join(re.sub(COMPANY_NOISE, " ", text).split())


def are_probable_duplicates(a, b) -> bool:
    """a et b : lignes (namedtuple) avec platform, norm_title, published_on."""
    if a.platform == b.platform:
        return False
    if pd.notna(a.published_on) and pd.notna(b.published_on):
        if abs((a.published_on - b.published_on).days) > MAX_DAYS_APART:
            return False
    return SequenceMatcher(None, a.norm_title, b.norm_title).ratio() >= TITLE_SIMILARITY


def find_probable_duplicates(df: pd.DataFrame) -> dict[int, list[int]]:
    """{id d'une offre: [ids de ses doublons probables]}, uniquement pour les offres concernées.

    Les comparaisons se font seulement entre offres de la même entreprise normalisée :
    quelques secondes au plus, même pour des dizaines de milliers d'offres.
    """
    work = pd.DataFrame({
        Col.ID: df[Col.ID],
        "platform": df[Col.PLATFORM],
        "published_on": pd.to_datetime(df[Col.PUBLISHED_ON], errors="coerce"),
        "norm_company": df[Col.COMPANY].fillna("").map(normalize_company),
        "norm_title": df[Col.TITLE].fillna("").map(normalize_title),
    })
    work = work[work["norm_company"] != ""]

    duplicates: dict[int, list[int]] = {}
    for _, group in work.groupby("norm_company"):
        if len(group) < 2 or group["platform"].nunique() < 2:
            continue
        rows = list(group.itertuples(index=False))
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if are_probable_duplicates(a, b):
                    duplicates.setdefault(int(a.id), []).append(int(b.id))
                    duplicates.setdefault(int(b.id), []).append(int(a.id))
    return duplicates
