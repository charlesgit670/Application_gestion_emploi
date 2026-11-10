"""Scraper LinkedIn, via les pages publiques "invité" (sans connexion).

Deux phases :
    1. liste des offres via l'API de pagination  /jobs-guest/jobs/api/seeMoreJobPostings
    2. détail de chaque offre via               /jobs-guest/jobs/api/jobPosting/<id>
LinkedIn limite fortement le débit (HTTP 429) : pause aléatoire entre deux offres,
et nouvelles tentatives automatiques gérées par BaseScraper.fetch.
"""
import logging
import math
import random
import re
import time
from datetime import date
from urllib.parse import urlsplit

from jobfinder.scrapers.base import BaseScraper, ProgressCallback, RawJob
from jobfinder.scrapers.keywords import build_keyword_urls

logger = logging.getLogger(__name__)

SEARCH_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{query}&start={start}"
DETAIL_API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
PAGE_SIZE = 10


class Linkedin(BaseScraper):
    key = "linkedin"
    label = "LinkedIn"
    default_keyword_mode = "or"

    def search_urls(self) -> list[str]:
        template = re.sub(r"keywords=[^&]*", "keywords={keyword}", self.search_url)
        return build_keyword_urls(template, self.keywords, self.keyword_mode,
                                  encode_mode="query", quote_terms_for_or=True)

    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        jobs_by_id: dict[str, RawJob] = {}  # l'identifiant LinkedIn sert au dédoublonnage
        for url in self.search_urls():
            try:
                jobs_by_id.update(self._read_search(url, known_ids=set(jobs_by_id)))
            except Exception as exc:
                logger.warning("LinkedIn : recherche ignorée (%s) : %s", exc, url)

        logger.info("LinkedIn : %d offre(s) trouvée(s), lecture des détails...", len(jobs_by_id))
        return self.fetch_details(list(jobs_by_id.values()), progress, self._read_details)

    def _read_search(self, url: str, known_ids: set[str]) -> dict[str, RawJob]:
        counter = self.fetch_soup(url).find("span", class_="results-context-header__job-count")
        total = int(re.sub(r"\D", "", counter.get_text()) or 0) if counter else 0
        query = urlsplit(url).query
        if not total or not query:
            logger.info("LinkedIn : aucun résultat pour %s", url)
            return {}

        found = {}
        for page in range(math.ceil(total / PAGE_SIZE)):
            try:
                soup = self.fetch_soup(SEARCH_API.format(query=query, start=page * PAGE_SIZE))
            except Exception as exc:
                # LinkedIn finit souvent par bloquer (HTTP 429) : on garde ce qui a été trouvé
                logger.warning("LinkedIn : pagination interrompue page %d (%s), %d offre(s) conservée(s)",
                               page + 1, exc, len(found))
                break
            items = soup.find_all("li")
            if not items:  # fin réelle des résultats (le compteur affiché est souvent surestimé)
                break
            time.sleep(random.uniform(0.5, 1.5))

            for item in items:
                card = item.find("div", class_="base-card")
                anchor = item.find("a")
                time_tag = item.find("time")
                if card is None or anchor is None or time_tag is None:
                    continue

                # data-entity-urn = "urn:li:jobPosting:1234567890"
                job_id = card.get("data-entity-urn", "").split(":")[-1].strip()
                if not job_id or job_id in known_ids or job_id in found:
                    continue
                published_on = _parse_iso_date(time_tag.get("datetime"))
                if not self.is_recent(published_on):
                    continue

                # Titre et entreprise sont complétés lors de la lecture du détail
                found[job_id] = RawJob(title="", company="", link=anchor.get("href", ""),
                                       published_on=published_on, source_id=job_id)
        return found

    def _read_details(self, job: RawJob) -> str:
        """Lit la fiche détaillée : complète titre et entreprise, renvoie la description."""
        time.sleep(random.uniform(0.5, 2.5))  # rester discret pour limiter les HTTP 429
        soup = self.fetch_soup(DETAIL_API.format(job_id=job.source_id))

        logo = soup.select_one("div.top-card-layout__card a img")
        title = soup.select_one("div.top-card-layout__entity-info a")
        description = soup.select_one("div.show-more-less-html__markup")
        if not (logo and logo.get("alt") and title and description):
            raise ValueError("structure de la page inattendue")

        job.company = logo.get("alt")
        job.title = title.get_text(strip=True)
        return description.get_text(separator="\n", strip=True)


def _parse_iso_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None
