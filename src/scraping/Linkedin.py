from tqdm import tqdm
import json
import re
import math
import time
from urllib.parse import urlsplit
from datetime import datetime as dt, timedelta
import random
from bs4 import BeautifulSoup
import backoff
from requests.exceptions import RequestException, HTTPError

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, build_keyword_urls

class Linkedin(JobFinder):

    def __init__(self):
        self.get_config()
        # self.keywords = ["Data Scientist", "Machine Learning"]
        # self.url = 'https://www.linkedin.com/jobs/search?keywords={}&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0'
        # self.job_id_api = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={}&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0&start={}'
        self.job_description_api = 'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}'

    def _parse_total_offer(self, count_text):
        if not count_text:
            return 0
        digits = re.sub(r"[^\d]", "", count_text)
        return int(digits) if digits else 0

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url_template = re.sub(r'keywords=[^&]*', 'keywords={keyword}', config['url']['linkedin'])
        self.keyword_mode = config.get("keyword_mode", {}).get("linkedin", "or")
        self.filter_day_scrap = int(config["filter_day_scrap"])

    def build_urls(self):
        return build_keyword_urls(
            base_url=self.url_template,
            keywords=self.keywords,
            mode=self.keyword_mode,
            encode_mode="query",
            quote_terms_for_or=True,
        )

    def _extract_job_id_from_urn(self, urn):
        urn = (urn or "").strip()
        if ":" not in urn:
            return None
        parts = [part for part in urn.split(":") if part]
        if not parts:
            return None
        job_id = parts[-1].strip()
        return job_id or None

    def _parse_job_datetime(self, raw_datetime):
        try:
            return dt.fromisoformat(raw_datetime)
        except (TypeError, ValueError):
            print(f"Date LinkedIn invalide, offre ignorée: {raw_datetime}")
            return None

    @measure_time
    def getJob(self, update_callback=None):
        all_job_id = []
        all_job_link = []
        all_job_datetime = []

        total_pagination_steps = 0
        completed_steps = 0

        for search_url in self.build_urls():
            # Récupérer le nombre total d'offre pour chaque URL de recherche
            res = self.get_content(search_url)
            soup = BeautifulSoup(res.text, 'html.parser')
            span = soup.find('span', class_='results-context-header__job-count')
            if span is None:
                print(f"Compteur d'offres LinkedIn introuvable, recherche ignorée: {search_url}")
                continue

            total_offer = self._parse_total_offer(span.get_text())
            if not total_offer:
                print(f"Compteur d'offres LinkedIn illisible ('{span.get_text(strip=True)}'), recherche ignorée: {search_url}")
                continue

            query_string = urlsplit(search_url).query
            if not query_string:
                print(f"URL LinkedIn ignorée (query manquante): {search_url}")
                continue

            page_count = math.ceil(total_offer / 10)
            total_pagination_steps += page_count
            job_id_api = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + query_string + "&start={}"

            # Récupérer tous les job id
            for i in range(0, page_count):
                res = self.get_content(job_id_api.format(i * 10))
                if res is None:
                    completed_steps += 1
                    if update_callback:
                        update_callback(completed_steps, total_pagination_steps + max(len(all_job_id), 1))
                    continue
                soup = BeautifulSoup(res.text, 'html.parser')
                alljobs_on_this_page = soup.find_all("li")
                for job_on_this_page in alljobs_on_this_page:
                    base_card = job_on_this_page.find("div", {"class": "base-card"})
                    if base_card is None:
                        continue

                    jobid = self._extract_job_id_from_urn(base_card.get('data-entity-urn', ''))
                    if not jobid:
                        print("Offre LinkedIn ignorée (job id absent/invalide).")
                        continue

                    link_tag = job_on_this_page.find("a")
                    joblink = link_tag.get("href", "") if link_tag else ""
                    if not joblink:
                        continue

                    time_tag = job_on_this_page.find("time")
                    jobDateTime = time_tag.get("datetime") if time_tag else None
                    if not jobDateTime:
                        print("Date LinkedIn invalide, offre ignorée: datetime manquant")
                        continue

                    # on filtre les offres trop ancienne
                    date_limit = dt.now() - timedelta(days=self.filter_day_scrap)
                    job_datetime_obj = self._parse_job_datetime(jobDateTime)
                    if job_datetime_obj is None:
                        continue

                    if job_datetime_obj >= date_limit and jobid not in all_job_id:
                        all_job_id.append(jobid)
                        all_job_link.append(joblink)
                        all_job_datetime.append(jobDateTime)

                completed_steps += 1
                if update_callback:
                    update_callback(completed_steps, total_pagination_steps + max(len(all_job_id), 1))
        print(f"Nombre de fiche de poste Linkedin récupéré {len(all_job_id)}")

        # Récupérer le contenu de toutes les fiches de poste
        list_title = []
        list_content = []
        list_company = []
        list_link = all_job_link
        list_datetime = all_job_datetime

        total = len(all_job_id)
        total_steps = total_pagination_steps + max(total, 1)
        for i, job_id in enumerate(all_job_id):
        # for job_id in tqdm(all_job_id):
            try:
                company, jobTitle, jobDescription = self.get_job_details(job_id)
                list_title.append(jobTitle)
                list_content.append(jobDescription)
                list_company.append(company)
            except Exception as exc:
                print(f"Détails LinkedIn ignorés pour {job_id}: {exc}")
                if update_callback:
                    update_callback(total_pagination_steps + i + 1, total_steps)
                continue

            print(f"Linkedin {i}/{total}")
            if update_callback:
                update_callback(total_pagination_steps + i + 1, total_steps)

        if update_callback:
            update_callback(total_steps, total_steps)

        df = self.formatData("linkedin", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df

    @backoff.on_exception(backoff.expo, (HTTPError, RequestException), giveup=lambda e: e.response is not None and e.response.status_code != 429)
    def get_job_details(self, job_id):
        time.sleep(random.uniform(0.5, 2.5))
        resp = self.get_content(self.job_description_api.format(job_id))

        if resp is None or resp.status_code == 429:
            raise HTTPError(response=resp)

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Guard: top-card-layout__card
        card = soup.find("div", {"class": "top-card-layout__card"})
        if not card:
            raise ValueError("Could not find top-card-layout__card")
        link = card.find("a")
        if not link:
            raise ValueError("Could not find link in card")
        img = link.find("img")
        if not img:
            raise ValueError("Could not find img in link")
        company = img.get('alt')
        if not company:
            raise ValueError("Could not find alt text for company")

        # Guard: top-card-layout__entity-info
        entity_info = soup.find("div", {"class": "top-card-layout__entity-info"})
        if not entity_info:
            raise ValueError("Could not find top-card-layout__entity-info")
        title_link = entity_info.find("a")
        if not title_link:
            raise ValueError("Could not find link in entity-info")
        jobTitle = title_link.text.strip()
        if not jobTitle:
            raise ValueError("Could not extract job title")

        # Guard: show-more-less-html__markup
        description_div = soup.find("div",
                                   class_="show-more-less-html__markup show-more-less-html__markup--clamp-after-5 relative overflow-hidden")
        if not description_div:
            raise ValueError("Could not find description div")
        jobDescription = description_div.get_text(separator="\n", strip=True)
        if not jobDescription:
            raise ValueError("Could not extract job description")

        return company, jobTitle, jobDescription


if __name__ == "__main__":
    job = Linkedin()
    df = job.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")
