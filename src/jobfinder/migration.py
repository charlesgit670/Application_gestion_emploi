"""Migration unique de l'ancien fichier data/job.csv vers la base SQLite.

Correspondance des anciens booléens vers le nouveau statut (règle R1) :

    is_refused = 1                  -> REFUSEE
    is_apply   = 1                  -> POSTULEE
    is_read    = 1                  -> LUE
    sinon                           -> NOUVELLE

    score = -1                      -> score vide (offre non évaluée)
    is_good_offer = 1 et score < 50 -> forced_relevant = 1 (offre réhabilitée à la main)
    is_good_offer = 0 et score vide -> score = 0 (écartée sans score, ex : pré-filtre)

Le CSV d'origine n'est jamais modifié ni supprimé.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from jobfinder.models import Col, Status
from jobfinder.paths import LEGACY_CSV_PATH
from jobfinder.storage import JobStore

logger = logging.getLogger(__name__)

LEGACY_THRESHOLD = 50  # seuil codé en dur dans l'ancienne version


def convert_legacy_dataframe(old: pd.DataFrame) -> pd.DataFrame:
    """Convertit un DataFrame au format CSV historique vers le format de la base."""
    def flag(name: str) -> pd.Series:
        return pd.to_numeric(old.get(name, 0), errors="coerce").fillna(0).astype(int) == 1

    is_read, is_apply, is_refused, is_good = (
        flag("is_read"), flag("is_apply"), flag("is_refused"), flag("is_good_offer")
    )

    # Statut : le plus "avancé" l'emporte (np.select prend la première condition vraie)
    status = np.select(
        [is_refused, is_apply, is_read],
        [Status.REFUSEE.value, Status.POSTULEE.value, Status.LUE.value],
        default=Status.NOUVELLE.value,
    )

    score = pd.to_numeric(old["score"], errors="coerce")
    score = score.where(score >= 0)  # -1 -> vide
    rejected_without_score = ~is_good & score.isna()
    score = score.mask(rejected_without_score, 0)

    forced = (is_good & (score < LEGACY_THRESHOLD)).astype(int)

    published = pd.to_datetime(old["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return pd.DataFrame({
        Col.HASH: old["hash"],
        Col.LINK: old["link"],
        Col.PLATFORM: old["platform"],
        Col.TITLE: old["title"],
        Col.COMPANY: old["company"],
        Col.CONTENT: old["content"],
        Col.PUBLISHED_ON: published,
        Col.SCORE: score.astype("Int64"),
        Col.AI_COMMENT: old.get("comment"),
        Col.CUSTOM_PROFILE: old.get("custom_profile"),
        Col.FORCED_RELEVANT: forced,
        Col.STATUS: status,
    })


def migrate_legacy_csv(store: JobStore, csv_path: Path = LEGACY_CSV_PATH) -> int:
    """Importe l'ancien CSV si la base est vide. Retourne le nombre d'offres importées."""
    if not csv_path.exists() or store.count() > 0:
        return 0

    logger.info("Migration de %s vers la base SQLite...", csv_path.name)
    old = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    added = store.insert(convert_legacy_dataframe(old))
    logger.info("Migration terminée : %d / %d offres importées", added, len(old))
    return added
