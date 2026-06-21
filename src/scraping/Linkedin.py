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

    def _parse_total_offer(self, text):
        try:
            return int(text.strip())
        except (ValueError, AttributeError):
            return 0

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

    @measure_time
    def getJob(self, update_callback=None):
        all_job_id = []
        all_job_link = []
        all_job_datetime = []

        for search_url in self.build_urls():
            res = self.get_content(search_url)
            soup = BeautifulSoup(res.text, 'html.parser')
            span = soup.find('span', class_='results-context-header__job-count')
            if span is None:
                continue
            total_offer = self._parse_total_offer(span.get_text())

            query_string = urlsplit(search_url).query
            if not query_string:
                continue
            job_id_api = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + query_string + "&start={}"

            for i in range(0, math.ceil(total_offer / 10)):
                res = self.get_content(job_id_api.format(i * 10))
                if res is None:
                    continue
                soup = BeautifulSoup(res.text, 'html.parser')
                alljobs_on_this_page = soup.find_all("li")
                for job_on_this_page in alljobs_on_this_page:
                    base_card = job_on_this_page.find("div", {"class": "base-card"})
                    if base_card is None:
                        continue

                    jobid = self._extract_job_id_from_urn(base_card.get('data-entity-urn', ''))
                    if not jobid:
                        continue

                    link_tag = job_on_this_page.find("a")
                    joblink = link_tag.get("href", "") if link_tag else ""
                    if not joblink:
                        continue

                    time_tag = job_on_this_page.find("time")
                    jobDateTime = time_tag.get("datetime") if time_tag else None
                    if not jobDateTime:
                        continue

                    date_limit = dt.now() - timedelta(days=self.filter_day_scrap)
                    job_datetime_obj = dt.fromisoformat(jobDateTime)

                    if job_datetime_obj >= date_limit and jobid not in all_job_id:
                        all_job_id.append(jobid)
                        all_job_link.append(joblink)
                        all_job_datetime.append(jobDateTime)

        print(f"Nombre de fiche de poste Linkedin récupéré {len(all_job_id)}")

        list_title = []
        list_content = []
        list_company = []
        list_link = all_job_link
        list_datetime = all_job_datetime

        total = len(all_job_id)
        for i, job_id in enumerate(all_job_id):
        # for job_id in tqdm(all_job_id):
            company, jobTitle, jobDescription = self.get_job_details(job_id)
            list_title.append(jobTitle)
            list_content.append(jobDescription)
            list_company.append(company)
            print(f"Linkedin {i}/{total}")
            if update_callback:
                update_callback(i + 1, total)

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

        company = soup.find("div", {"class": "top-card-layout__card"}).find("a").find("img").get('alt')
        jobTitle = soup.find("div", {"class": "top-card-layout__entity-info"}).find("a").text.strip()
        jobDescription = soup.find("div",
                                   class_="show-more-less-html__markup show-more-less-html__markup--clamp-after-5 relative overflow-hidden") \
                             .get_text(separator="\n", strip=True)

        return company, jobTitle, jobDescription


if __name__ == "__main__":
    job = Linkedin()
    df = job.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")
