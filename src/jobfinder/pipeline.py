"""Pipeline complet d'une mise à jour des offres.

    1. Scraping des plateformes cochées (en parallèle si use_multithreading)
    2. Ne garder que les offres absentes de la base (hash ou lien inconnus)
    3. Filtre de langue          -> offres enregistrées avec score 0
    4. Pré-filtre par mots       -> offres enregistrées avec score 0 (règle R3)
    5. Enregistrement en base    -> les offres sont sauvées AVANT le LLM :
                                    un plantage du LLM ne fait plus rien perdre
    6. Évaluation LLM de toutes les offres nouvelles non évaluées, y compris
       celles qui avaient échoué lors d'un scraping précédent (règle R6).
       Chaque score est enregistré dès qu'il est reçu.

Utilisation depuis du code (l'interface lit `progress` pendant l'exécution) :
    progress = PipelineProgress()
    report = await run_pipeline(load_config(), JobStore(), progress)

En ligne de commande, depuis le dossier src/ :
    python -m jobfinder.pipeline
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

import pandas as pd

from jobfinder.config import AppConfig, load_config
from jobfinder.filters import is_language_allowed, pre_filter_reason
from jobfinder.llm import LlmScorer
from jobfinder.models import PLATFORM_LABELS, Col
from jobfinder.scrapers import SCRAPERS
from jobfinder.storage import JobStore

logger = logging.getLogger(__name__)

LLM_TASK = "Évaluation LLM"
LANGUAGE_COMMENT = "Écartée : langue non autorisée"


# ---------------------------------------------------------------------------
# Suivi de l'avancement (lu par l'interface pendant que le pipeline tourne)
# ---------------------------------------------------------------------------
@dataclass
class TaskProgress:
    current: int = 0
    total: int = 0
    state: str = "en attente"  # en attente | en cours | terminé | erreur
    detail: str = ""

    @property
    def ratio(self) -> float:
        return self.current / self.total if self.total else (1.0 if self.state == "terminé" else 0.0)


@dataclass
class PipelineProgress:
    tasks: dict[str, TaskProgress] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    running: bool = False

    def task(self, name: str) -> TaskProgress:
        return self.tasks.setdefault(name, TaskProgress())

    def say(self, message: str) -> None:
        """Message affiché dans l'interface et écrit dans le journal."""
        logger.info(message)
        self.messages.append(f"{time.strftime('%H:%M:%S')}  {message}")


@dataclass
class PipelineReport:
    scraped: dict[str, int] = field(default_factory=dict)    # offres récupérées par plateforme
    failed_platforms: dict[str, str] = field(default_factory=dict)
    new: int = 0                # offres absentes de la base
    wrong_language: int = 0
    pre_filtered: int = 0
    inserted: int = 0
    scored: int = 0
    llm_failures: int = 0


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------
async def scrape_all(config: AppConfig, progress: PipelineProgress, report: PipelineReport,
                     scrapers: dict = SCRAPERS) -> pd.DataFrame:
    """Étape 1 : lance les scrapers (chacun dans un thread) et concatène leurs offres."""

    def run_one(key: str) -> pd.DataFrame:
        label = PLATFORM_LABELS.get(key, key)
        task = progress.task(label)
        task.state = "en cours"

        def on_progress(current: int, total: int) -> None:
            task.current, task.total = current, total

        try:
            df = scrapers[key](config).run(on_progress)
            task.state, task.detail = "terminé", f"{len(df)} offre(s)"
            report.scraped[key] = len(df)
            return df
        except Exception as exc:  # un site en panne ne bloque pas les autres
            logger.exception("Échec du scraping %s", label)
            task.state, task.detail = "erreur", str(exc)
            report.failed_platforms[key] = str(exc)
            return pd.DataFrame()

    keys = config.active_platforms()
    for key in keys:
        progress.task(PLATFORM_LABELS.get(key, key))  # affiche toutes les barres dès le début

    if config.use_multithreading:
        frames = await asyncio.gather(*(asyncio.to_thread(run_one, key) for key in keys))
    else:
        frames = [await asyncio.to_thread(run_one, key) for key in keys]

    frames = [df for df in frames if not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def keep_new_offers(scraped: pd.DataFrame, store: JobStore) -> pd.DataFrame:
    """Étape 2 : retire les offres déjà en base (même hash ou même lien)."""
    if scraped.empty:
        return scraped
    known_hashes, known_links = store.known_keys()
    is_known = scraped[Col.HASH].isin(known_hashes) | scraped[Col.LINK].isin(known_links)
    return scraped[~is_known].drop_duplicates(subset=Col.LINK)


def rejection_reason(title: str, content: str, config: AppConfig) -> str | None:
    """Motif de rejet avant LLM (langue puis pré-filtre), ou None si l'offre passe."""
    if not is_language_allowed(content, config.language_filter):
        return LANGUAGE_COMMENT
    return pre_filter_reason(title, content, config.pre_filter)


def apply_filters(new: pd.DataFrame, config: AppConfig, report: PipelineReport) -> pd.DataFrame:
    """Étapes 3 et 4 : filtre de langue puis pré-filtre.

    Les offres rejetées sont CONSERVÉES avec un score de 0 et le motif en commentaire :
    elles apparaissent dans « Écartées » et ne reviennent pas comme nouvelles au
    scraping suivant (règle R3, étendue à la langue).
    """
    if new.empty:
        return new
    new = new.copy()
    reasons = [
        rejection_reason(row.title, row.content if isinstance(row.content, str) else "", config)
        for row in new.itertuples()
    ]
    new[Col.SCORE] = [0 if reason else None for reason in reasons]
    new[Col.AI_COMMENT] = reasons
    report.wrong_language = reasons.count(LANGUAGE_COMMENT)
    report.pre_filtered = sum(reason is not None for reason in reasons) - report.wrong_language
    return new


async def score_pending_offers(config: AppConfig, store: JobStore, progress: PipelineProgress,
                               report: PipelineReport, scorer=None) -> None:
    """Étape 6 : évalue avec le LLM toutes les offres nouvelles encore sans score."""
    ids = set(store.unscored_ids())
    if not ids:
        return
    jobs = store.load()
    jobs = jobs[jobs[Col.ID].isin(ids)]

    task = progress.task(LLM_TASK)
    task.state, task.total = "en cours", len(jobs)
    progress.say(f"Évaluation de {len(jobs)} offre(s) par le LLM ({config.llm.provider})...")
    scorer = scorer or LlmScorer(config.llm)

    async def score_one(job) -> None:
        try:
            content = job.content if isinstance(job.content, str) else ""  # NaN -> ""
            verdict = await scorer.score(job.title, job.company, content)
            store.set_ai_result(job.id, verdict.score, verdict.justification)
            report.scored += 1
        except Exception as exc:  # l'offre reste sans score : nouvel essai au prochain scraping
            report.llm_failures += 1
            logger.warning("LLM : échec sur « %s » (%s: %s)", job.title, type(exc).__name__, exc)
        finally:
            task.current += 1

    await asyncio.gather(*(score_one(job) for job in jobs.itertuples()))
    task.state = "terminé"
    task.detail = f"{report.scored} évaluée(s)" + (f", {report.llm_failures} échec(s)" if report.llm_failures else "")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def run_pipeline(config: AppConfig, store: JobStore, progress: PipelineProgress | None = None,
                       scrapers: dict = SCRAPERS, scorer=None) -> PipelineReport:
    """Exécute toutes les étapes. `scrapers` et `scorer` sont remplaçables (tests)."""
    progress = progress or PipelineProgress()
    report = PipelineReport()

    errors = config.scraping_errors()
    if errors:
        raise ValueError("Configuration incomplète : " + " ".join(errors))

    progress.running = True
    try:
        store.backup()
        progress.say("Scraping : " + ", ".join(PLATFORM_LABELS.get(k, k) for k in config.active_platforms()))
        scraped = await scrape_all(config, progress, report, scrapers)

        new = keep_new_offers(scraped, store)
        report.new = len(new)
        new = apply_filters(new, config, report)
        report.inserted = store.insert(new)
        progress.say(
            f"{len(scraped)} offre(s) récupérée(s), {report.new} nouvelle(s) : "
            f"{report.wrong_language} hors langue et {report.pre_filtered} pré-filtrée(s) (score 0), "
            f"{report.inserted} enregistrée(s)."
        )

        if config.use_llm:
            await score_pending_offers(config, store, progress, report, scorer)
        progress.say("Mise à jour terminée.")
        return report
    finally:
        progress.running = False


if __name__ == "__main__":
    from jobfinder.logs import setup_logging
    from jobfinder.migration import migrate_legacy_csv

    setup_logging()
    job_store = JobStore()
    migrate_legacy_csv(job_store)
    print(asyncio.run(run_pipeline(load_config(), job_store)))
