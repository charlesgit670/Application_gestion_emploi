"""Socle commun à tous les scrapers.

Chaque site est une classe qui hérite de `BaseScraper` et implémente une seule
méthode, `scrape()`, qui renvoie une liste de `RawJob`. Tout le reste est commun :
    - lecture de la configuration (mots-clés, URL, ancienneté max...) ;
    - requêtes HTTP avec timeout et nouvelles tentatives automatiques ;
    - filtre d'ancienneté ;
    - mise en forme finale en DataFrame (hash, dédoublonnage).

Ajouter un site = écrire une classe de ~80 lignes, puis l'enregistrer dans
scrapers/__init__.py.
"""
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import backoff
import pandas as pd
import requests
from bs4 import BeautifulSoup

from jobfinder.config import AppConfig
from jobfinder.models import Col

logger = logging.getLogger(__name__)

# Fonction appelée pour signaler l'avancement : progress(nb_traitées, nb_total)
ProgressCallback = Callable[[int, int], None]

REQUEST_TIMEOUT = 30  # secondes ; sans timeout, un site muet bloquait le scraping indéfiniment
RETRYABLE_STATUS = {429, 500, 502, 503, 504}  # erreurs temporaires : on réessaie
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class TemporaryHttpError(Exception):
    """Réponse HTTP temporaire (trop de requêtes, serveur surchargé...)."""


@dataclass
class RawJob:
    """Une offre telle que récupérée sur un site, avant tout traitement."""
    title: str
    company: str
    link: str
    content: str = ""
    published_on: date | None = None  # None = date inconnue
    source_id: str = ""  # identifiant de l'offre sur le site (utile pour lire son détail)


def compute_hash(platform: str, title: str, company: str, content: str) -> str:
    """Empreinte d'une offre. Formule identique à l'ancienne version (compatibilité de la base)."""
    return hashlib.sha256((platform + title + company + content).encode("utf-8")).hexdigest()


class BaseScraper(ABC):
    """Classe mère des scrapers. Les sous-classes définissent `key`, `label` et `scrape()`."""

    key: str = ""                        # clé courte utilisée dans config.json ("hw", "apec"...)
    label: str = ""                      # nom affiché
    default_keyword_mode: str = "one_by_one"

    def __init__(self, config: AppConfig):
        self.keywords = config.keywords
        self.search_url = config.url.get(self.key, "")
        self.keyword_mode = config.keyword_mode.get(self.key, self.default_keyword_mode)
        self.max_age_days = config.filter_day_scrap
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------- à implémenter
    @abstractmethod
    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        """Récupère les offres du site (avec leur description)."""

    # ----------------------------------------------------------------- HTTP
    @backoff.on_exception(
        backoff.expo,
        (requests.ConnectionError, requests.Timeout, TemporaryHttpError),
        max_tries=5,
        jitter=backoff.full_jitter,
    )
    def fetch(self, url: str) -> requests.Response:
        """GET avec timeout. Réessaie jusqu'à 5 fois sur erreur réseau ou erreur temporaire."""
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code in RETRYABLE_STATUS:
            raise TemporaryHttpError(f"HTTP {response.status_code} sur {url}")
        response.raise_for_status()  # 404, 403... : erreur définitive
        return response

    def fetch_soup(self, url: str) -> BeautifulSoup:
        """Page HTML prête à être explorée avec BeautifulSoup."""
        return BeautifulSoup(self.fetch(url).text, "html.parser")

    # --------------------------------------------------------------- outils
    def is_recent(self, published_on: date | None) -> bool:
        """Vrai si l'offre respecte l'ancienneté max. Une date inconnue est conservée."""
        if published_on is None:
            return True
        return published_on >= date.today() - timedelta(days=self.max_age_days)

    def fetch_details(self, jobs: list[RawJob], progress: ProgressCallback,
                      read_description: Callable[[RawJob], str], pause: float = 0.0) -> list[RawJob]:
        """Boucle commune « page de détail » : remplit la description de chaque offre.

        Une offre en erreur est ignorée (et journalisée) sans arrêter les autres.
        """
        complete = []
        for i, job in enumerate(jobs, start=1):
            try:
                job.content = read_description(job)
                if job.content:
                    complete.append(job)
                else:
                    logger.warning("%s : description vide, offre ignorée (%s)", self.label, job.link)
            except Exception as exc:  # une offre cassée ne doit pas arrêter le scraping
                logger.warning("%s : échec sur %s (%s)", self.label, job.link, exc)
            progress(i, len(jobs))
            if pause:
                time.sleep(pause)
        return complete

    # ------------------------------------------------------------ point d'entrée
    def run(self, progress: ProgressCallback | None = None) -> pd.DataFrame:
        """Lance le scraping et renvoie un DataFrame prêt à être inséré en base."""
        progress = progress or (lambda current, total: None)
        start = time.perf_counter()

        jobs = self.scrape(progress)
        df = self.to_dataframe(jobs)

        logger.info("%s : %d offre(s) en %.0f s", self.label, len(df), time.perf_counter() - start)
        return df

    def to_dataframe(self, jobs: list[RawJob]) -> pd.DataFrame:
        """Liste de RawJob -> DataFrame avec plateforme et hash, sans doublon."""
        columns = [Col.TITLE, Col.COMPANY, Col.LINK, Col.CONTENT, Col.PUBLISHED_ON]
        if not jobs:
            return pd.DataFrame(columns=columns + [Col.PLATFORM, Col.HASH])

        df = pd.DataFrame([asdict(job) for job in jobs]).drop(columns="source_id")
        df = df.rename(columns={"published_on": Col.PUBLISHED_ON})
        df[Col.PLATFORM] = self.key
        df[Col.HASH] = [
            compute_hash(self.key, row.title, row.company, row.content)
            for row in df.itertuples()
        ]
        return df.drop_duplicates(subset=Col.LINK).drop_duplicates(subset=Col.HASH).reset_index(drop=True)


def unique_by_link(jobs: list[RawJob]) -> list[RawJob]:
    """Retire les offres en double (même lien), en gardant la première."""
    seen, unique = set(), []
    for job in jobs:
        if job.link not in seen:
            seen.add(job.link)
            unique.append(job)
    return unique
