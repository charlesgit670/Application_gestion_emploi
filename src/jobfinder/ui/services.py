"""Données et traitements partagés par toutes les pages de l'interface.

Les pages n'accèdent jamais directement à SQLite ou au pipeline : elles passent par
ce module. Ainsi la logique (quelles offres sont « à traiter », comment lancer un
scraping...) est écrite une seule fois et reste testable sans interface.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from jobfinder.config import AppConfig, load_config
from jobfinder.duplicates import find_probable_duplicates
from jobfinder.models import ACTIVE_APPLICATION, Col, Status, new_relevant_offers, offers_rejected_by_ai
from jobfinder.pipeline import PipelineProgress, PipelineReport, run_pipeline
from jobfinder.storage import JobStore

logger = logging.getLogger(__name__)

store = JobStore()  # une seule base pour toute l'application


# ---------------------------------------------------------------------------
# Vues : quelles offres apparaissent dans quelle liste
# ---------------------------------------------------------------------------
def view_todo(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Offres à traiter : les plus récentes d'abord, puis par score."""
    return new_relevant_offers(df, threshold).sort_values(
        [Col.DAYS_OLD, Col.SCORE], ascending=[True, False], na_position="last")


def view_rejected(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Offres écartées (LLM, langue ou pré-filtre) : les mieux notées d'abord."""
    return offers_rejected_by_ai(df, threshold).sort_values(
        [Col.SCORE, Col.DAYS_OLD], ascending=[False, True], na_position="last")


def view_status(df: pd.DataFrame, *statuses: Status) -> pd.DataFrame:
    """Offres ayant l'un des statuts donnés, dernier changement en premier."""
    return df[df[Col.STATUS].isin(statuses)].sort_values(Col.STATUS_CHANGED_AT, ascending=False, na_position="last")


def days_without_news(df: pd.DataFrame) -> pd.Series:
    """Jours écoulés depuis la dernière activité (candidature, changement de statut ou relance)."""
    last_activity = pd.to_datetime(df[Col.STATUS_CHANGED_AT], errors="coerce").fillna(df[Col.APPLIED_ON])
    return (pd.Timestamp(date.today()) - last_activity.dt.normalize()).dt.days


def needs_follow_up(df: pd.DataFrame, follow_up_days: int) -> pd.DataFrame:
    """Candidatures sans nouvelle depuis `follow_up_days` jours (relance conseillée, règle R7)."""
    applied = df[df[Col.STATUS] == Status.POSTULEE]
    waiting = days_without_news(applied)
    # Les candidatures sans aucune date (importées de l'ancienne version) sont ignorées
    late = waiting.notna() & (waiting.fillna(0) >= follow_up_days)
    return applied[late].assign(days_waiting=waiting[late]).sort_values("days_waiting", ascending=False)


def counts(df: pd.DataFrame, config: AppConfig) -> dict[str, int]:
    """Nombre d'offres par liste (menu latéral et tableau de bord)."""
    threshold = config.llm.score_threshold
    status = df[Col.STATUS]
    return {
        "todo": len(new_relevant_offers(df, threshold)),
        "rejected": len(offers_rejected_by_ai(df, threshold)),
        "read": int((status == Status.LUE).sum()),
        "applied": int((status == Status.POSTULEE).sum()),
        "interview": int((status == Status.ENTRETIEN).sum()),  # candidatures au stade entretien
        "refused": int((status == Status.REFUSEE).sum()),
        "active": int(status.isin(ACTIVE_APPLICATION).sum()),
        "follow_up": len(needs_follow_up(df, config.follow_up_days)),
        "total": len(df),
    }


def interviews_done(df: pd.DataFrame) -> pd.Series:
    """Entretiens réalisés par offre. Une offre au statut ENTRETIEN en compte au moins un."""
    return df[Col.INTERVIEW_COUNT].where(df[Col.STATUS] != Status.ENTRETIEN, df[Col.INTERVIEW_COUNT].clip(lower=1))


def application_stats(df: pd.DataFrame) -> dict[str, float]:
    """Statistiques de candidature : volume, entretiens, taux d'entretien, refus."""
    interviews = interviews_done(df)
    sent = df[Col.STATUS].isin([Status.POSTULEE, Status.ENTRETIEN, Status.REFUSEE]) | (interviews > 0)
    with_interview = interviews > 0
    refused = df[Col.STATUS] == Status.REFUSEE
    return {
        "sent": int(sent.sum()),
        "with_interview": int(with_interview.sum()),
        "interview_rate": with_interview.sum() / sent.sum() if sent.sum() else 0.0,
        "interviews": int(interviews.sum()),
        "refused": int(refused.sum()),
        "refused_after_interview": int((refused & with_interview).sum()),
        "waiting": int((df[Col.STATUS] == Status.POSTULEE).sum()),
    }


def relevance_by_platform(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Part des offres évaluées jugées pertinentes (score >= seuil), par plateforme.

    Les offres non évaluées sont exclues du calcul ; une offre réhabilitée compte comme pertinente.
    """
    evaluated = df[df[Col.SCORE].notna()]
    relevant = (evaluated[Col.SCORE] >= threshold) | (evaluated[Col.FORCED_RELEVANT] == 1)
    table = pd.DataFrame({"evaluated": evaluated.groupby(Col.PLATFORM).size(),
                          "relevant": relevant.groupby(evaluated[Col.PLATFORM]).sum()}).fillna(0)
    table["percent"] = 100 * table["relevant"] / table["evaluated"]
    return table.sort_values("percent")


# ---------------------------------------------------------------------------
# Doublons probables entre plateformes (règle R5)
# ---------------------------------------------------------------------------
_duplicates_cache: dict = {"key": None, "value": {}}


def probable_duplicates() -> dict[int, list[int]]:
    """{id: [ids des doublons probables]}. Calcul (~1 s) refait seulement si de nouvelles
    offres sont arrivées : un changement de statut ne modifie pas les doublons."""
    with store._connect() as conn:
        key = conn.execute(f"SELECT COUNT(*), MAX({Col.ID}) FROM jobs").fetchone()
    if key != _duplicates_cache["key"]:
        _duplicates_cache["value"] = find_probable_duplicates(load_jobs())
        _duplicates_cache["key"] = key
    return _duplicates_cache["value"]


def duplicates_of(job_id: int) -> list[dict]:
    """Doublons probables d'une offre, avec leur plateforme et leur statut."""
    return [job for other in probable_duplicates().get(int(job_id), []) if (job := store.get(other))]


def load_jobs() -> pd.DataFrame:
    """Toutes les offres, sans les descriptions (chargées à la demande avec store.get)."""
    return store.load(with_content=False)


# ---------------------------------------------------------------------------
# Scraping en tâche de fond
# ---------------------------------------------------------------------------
@dataclass
class ScrapingRun:
    """État du dernier scraping. Partagé par tous les onglets du navigateur :
    on peut changer de page pendant le scraping et revenir suivre l'avancement."""
    progress: PipelineProgress = field(default_factory=PipelineProgress)
    report: PipelineReport | None = None
    error: str | None = None
    task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()


scraping = ScrapingRun()


def start_scraping() -> None:
    """Lance une mise à jour des offres en arrière-plan (ignoré si déjà en cours)."""
    if scraping.running:
        return
    scraping.progress = PipelineProgress()
    scraping.report, scraping.error = None, None

    async def worker() -> None:
        try:
            scraping.report = await run_pipeline(load_config(), store, scraping.progress)
        except Exception as exc:  # affiché dans l'interface
            logger.exception("Échec de la mise à jour")
            scraping.error = str(exc)

    scraping.task = asyncio.get_running_loop().create_task(worker())
