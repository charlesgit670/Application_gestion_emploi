"""Scraper Choisir le Service Public (pages HTML).

Particularité conservée : le filtre d'ancienneté n'est PAS appliqué, les offres
publiques restant souvent ouvertes longtemps après leur date de mise en ligne.
"""
import logging
import re

from jobfinder.scrapers.base import BaseScraper, ProgressCallback, RawJob, unique_by_link
from jobfinder.scrapers.dates import parse_french_date
from jobfinder.scrapers.keywords import build_keyword_urls

logger = logging.getLogger(__name__)


class ServicePublic(BaseScraper):
    key = "sp"
    label = "Service Public"

    def search_urls(self) -> list[str]:
        # Le mot-clé est dans le chemin : .../mot-cles/data%20scientist/...
        template = re.sub(r"mot-cles/[^/]*", "mot-cles/{keyword}", self.search_url)
        if not template.endswith("/"):
            template += "/"
        return build_keyword_urls(template, self.keywords, self.keyword_mode, encode_mode="path")

    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        jobs = []
        for url in self.search_urls():
            try:
                jobs += self._read_search(url)
            except Exception as exc:
                logger.warning("Service Public : recherche ignorée (%s) : %s", exc, url)

        jobs = unique_by_link(jobs)
        logger.info("Service Public : %d offre(s) trouvée(s), lecture des descriptions...", len(jobs))
        return self.fetch_details(jobs, progress, self._read_description)

    def _read_search(self, url: str) -> list[RawJob]:
        first_page = self.fetch_soup(url)
        page_links = first_page.select("ul.fr-pagination__list a.fr-pagination__link")
        numbers = [int(a.get_text(strip=True)) for a in page_links if a.get_text(strip=True).isdigit()]
        last_page = max(numbers, default=1)

        jobs = []
        for page in range(1, last_page + 1):
            soup = first_page if page == 1 else self.fetch_soup(f"{url}page/{page}")
            for item in soup.select("li.fr-col-12.item"):
                job = self._read_card(item)
                if job:
                    jobs.append(job)
        return jobs

    @staticmethod
    def _read_card(item) -> RawJob | None:
        anchor = item.select_one("a.is-same-domain")
        published = item.select_one("li.fr-icon-calendar-line")
        if anchor is None or published is None:
            return None

        # L'employeur (ministère...) est soit le texte alternatif d'un logo, soit un texte
        logo = item.select_one("img.fr-responsive-img")
        text_logo = item.select_one("div.fr-responsive-img")
        if logo is not None and logo.get("alt"):
            company = logo.get("alt")
        elif text_logo is not None:
            company = text_logo.get_text(strip=True)
        else:
            company = "Non spécifié"

        date_text = published.get_text(strip=True).replace("En ligne depuis le", "").strip()
        return RawJob(
            title=anchor.get_text(strip=True),
            company=company,
            link=anchor["href"],
            published_on=parse_french_date(date_text),
        )

    def _read_description(self, job: RawJob) -> str:
        block = self.fetch_soup(job.link).select_one("div.col-left.rte")
        return block.get_text(separator="\n", strip=True) if block else ""
