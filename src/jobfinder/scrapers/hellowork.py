"""Scraper HelloWork (pages HTML classiques)."""
import logging
import re

from jobfinder.scrapers.base import BaseScraper, ProgressCallback, RawJob, unique_by_link
from jobfinder.scrapers.dates import parse_relative_date
from jobfinder.scrapers.keywords import build_keyword_urls

logger = logging.getLogger(__name__)

BASE_URL = "https://www.hellowork.com"


class HelloWork(BaseScraper):
    key = "hw"
    label = "HelloWork"

    def search_urls(self) -> list[str]:
        # Le paramètre "k" de l'URL fournie est remplacé par chaque mot-clé
        template = re.sub(r"\bk=[^&]*", "k={keyword}", self.search_url)
        return build_keyword_urls(template, self.keywords, self.keyword_mode, encode_mode="query")

    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        jobs = []
        for url in self.search_urls():
            try:
                jobs += self._read_search(url)
            except Exception as exc:
                logger.warning("HelloWork : recherche ignorée (%s) : %s", exc, url)

        jobs = unique_by_link(jobs)
        logger.info("HelloWork : %d offre(s) trouvée(s), lecture des descriptions...", len(jobs))
        return self.fetch_details(jobs, progress, self._read_description)

    def _read_search(self, url: str) -> list[RawJob]:
        """Parcourt toutes les pages de résultats d'une recherche."""
        first_page = self.fetch_soup(url)
        page_buttons = first_page.select('nav.sm\\:flex button[name="p"]')
        numbers = [int(b.get_text(strip=True)) for b in page_buttons if b.get_text(strip=True).isdigit()]
        last_page = max(numbers, default=1)

        jobs = []
        for page in range(1, last_page + 1):
            soup = first_page if page == 1 else self.fetch_soup(f"{url}&p={page}")
            result_list = soup.find("ul", {"aria-label": "liste des offres"})
            if result_list is None:
                continue
            for item in result_list.find_all("li", recursive=False):
                job = self._read_card(item)
                if job and self.is_recent(job.published_on):
                    jobs.append(job)
        return jobs

    @staticmethod
    def _read_card(item) -> RawJob | None:
        """Extrait titre / entreprise / lien / date d'une carte de résultat (None si incomplète)."""
        anchor = item.find("a", attrs={"data-cy": "offerTitle"})
        title_block = anchor.find("h3") if anchor else None
        # Le <h3> contient le titre puis l'entreprise, dans des <span> (anciennement des <p>)
        parts = title_block.find_all(["span", "p"], recursive=False) if title_block else []
        date_block = item.find("div", class_="text-grey-500")
        if not parts or date_block is None:
            return None

        return RawJob(
            title=parts[0].get_text(strip=True),
            company=parts[1].get_text(strip=True) if len(parts) > 1 else "Non spécifié",
            link=BASE_URL + anchor.get("href", ""),
            published_on=parse_relative_date(date_block.get_text(strip=True)),
        )

    def _read_description(self, job: RawJob) -> str:
        soup = self.fetch_soup(job.link)
        block = soup.find("div", attrs={"data-truncate-text-target": "content"})
        return block.get_text(strip=True, separator="\n") if block else ""
