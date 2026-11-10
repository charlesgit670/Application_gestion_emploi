"""Scraper France Travail (pages HTML, pagination par tranches de 20 offres)."""
import logging
import re

from jobfinder.scrapers.base import BaseScraper, ProgressCallback, RawJob, unique_by_link
from jobfinder.scrapers.dates import parse_relative_date
from jobfinder.scrapers.keywords import build_keyword_urls

logger = logging.getLogger(__name__)

BASE_URL = "https://candidat.francetravail.fr"
PAGE_SIZE = 20


class FranceTravail(BaseScraper):
    key = "ft"
    label = "France Travail"

    def search_urls(self) -> list[str]:
        template = re.sub(r"motsCles=[^&]*", "motsCles={keyword}", self.search_url)
        # Le paramètre "range" (pagination) est retiré : il est ajouté page par page
        template = re.sub(r"([?&])range=[^&]*(&|$)", r"\1", template).rstrip("&?")
        return build_keyword_urls(template, self.keywords, self.keyword_mode, encode_mode="query")

    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        jobs = []
        for url in self.search_urls():
            try:
                jobs += self._read_search(url)
            except Exception as exc:
                logger.warning("France Travail : recherche ignorée (%s) : %s", exc, url)

        jobs = unique_by_link(jobs)
        logger.info("France Travail : %d offre(s) trouvée(s), lecture des descriptions...", len(jobs))
        return self.fetch_details(jobs, progress, self._read_description)

    def _read_search(self, url: str) -> list[RawJob]:
        first_page = self.fetch_soup(f"{url}&range=0-{PAGE_SIZE - 1}")
        # Le titre de la page commence par le nombre total d'offres : "42 offres d'emploi..."
        title = first_page.select_one("h1.title")
        first_word = title.get_text(strip=True).split()[0] if title else ""
        if not first_word.isdigit():
            logger.info("France Travail : nombre d'offres illisible dans le titre de %s", url)
            return []
        total = int(first_word)

        jobs = []
        for start in range(0, total, PAGE_SIZE):
            soup = first_page if start == 0 else self.fetch_soup(f"{url}&range={start}-{start + PAGE_SIZE - 1}")
            result_list = soup.find("ul", class_="result-list")
            if result_list is None:
                continue
            for item in result_list.find_all("li", recursive=False):
                job = self._read_card(item)
                if job and self.is_recent(job.published_on):
                    jobs.append(job)
        return jobs

    @staticmethod
    def _read_card(item) -> RawJob | None:
        anchor = item.select_one("a.media.with-fav")
        if anchor is None:
            return None
        title = anchor.select_one("div.media-body h2")
        company = anchor.select_one("div.media-body p.subtext")
        published = anchor.select_one("div.media-body p.date")
        if not (title and company and published):
            return None

        return RawJob(
            title=title.get_text(strip=True),
            company=company.get_text(strip=True),
            link=BASE_URL + anchor.get("href", ""),
            published_on=parse_relative_date(published.get_text(strip=True)),
        )

    def _read_description(self, job: RawJob) -> str:
        block = self.fetch_soup(job.link).find("div", class_="description")
        return block.get_text(strip=True, separator="\n") if block else ""
