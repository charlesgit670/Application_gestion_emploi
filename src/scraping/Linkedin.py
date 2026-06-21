from tqdm import tqdm
import pandas as pd
import json
import re
import math
import time
from datetime import datetime as dt, timedelta
import random
from bs4 import BeautifulSoup
import backoff
from requests.exceptions import RequestException, HTTPError
import urllib.parse

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time

class Linkedin(JobFinder):

    def __init__(self):
        self.get_config()
        # self.keywords = ["Data Scientist", "Machine Learning"]
        # self.url = 'https://www.linkedin.com/jobs/search?keywords={}&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0'
        # self.job_id_api = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={}&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0&start={}'
        self.job_description_api = 'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}'

    def _parse_total_offer(self, soup):
        span = soup.find('span', class_='results-context-header__job-count')
        if not span:
            return 0
        try:
            return int(span.get_text(strip=True))
        except (ValueError, AttributeError):
            return 0

    def _extract_job_id_from_urn(self, urn_str):
        if not urn_str:
            return None
        parts = urn_str.split(":")
        if len(parts) >= 4:
            return parts[3]
        return None

    def _parse_job_datetime(self, datetime_str):
        if not datetime_str:
            return None
        try:
            return dt.fromisoformat(datetime_str)
        except (ValueError, TypeError):
            return None

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url = re.sub(r'keywords=[^&]*', 'keywords={}', config['url']['linkedin'])
        self.job_id_api = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + self.url.split("search?")[1] + "&start={}"
        self.filter_day_scrap = int(config["filter_day_scrap"])

    @measure_time
    def getJob(self, update_callback=None):
        # Récupérer le nombre total d'offre
        keywords = self.build_keywords()
        res = self.get_content(self.url.format(keywords))
        soup = BeautifulSoup(res.text, 'html.parser')
        total_offer = self._parse_total_offer(soup)

        # Récupérer tous les job id
        all_job_id = []
        all_job_link = []
        all_job_datetime = []
        for i in range(0, math.ceil(total_offer / 10)):

            res = self.get_content(self.job_id_api.format(keywords, i * 10))
            soup = BeautifulSoup(res.text, 'html.parser')
            alljobs_on_this_page = soup.find_all("li")
            for job_on_this_page in alljobs_on_this_page:
                base_card = job_on_this_page.find("div", {"class": "base-card"})
                if not base_card:
                    continue
                urn = base_card.get('data-entity-urn')
                jobid = self._extract_job_id_from_urn(urn)
                if not jobid:
                    continue
                link_elem = job_on_this_page.find("a")
                if not link_elem:
                    continue
                joblink = link_elem.get("href")
                if not joblink:
                    continue
                time_elem = job_on_this_page.find("time")
                if not time_elem:
                    continue
                jobDateTime = time_elem.get("datetime")
                if not jobDateTime:
                    continue

                # on filtre les offres trop ancienne
                date_limit = dt.now() - timedelta(days=self.filter_day_scrap)
                job_datetime_obj = self._parse_job_datetime(jobDateTime)
                if not job_datetime_obj:
                    continue

                if job_datetime_obj >= date_limit:
                    if jobid not in all_job_id:
                        all_job_id.append(jobid)
                        all_job_link.append(joblink)
                        all_job_datetime.append(jobDateTime)
        print(f"Nombre de fiche de poste Linkedin récupéré {len(all_job_id)}")

        # Récupérer le contenu de toutes les fiches de poste
        list_title = []
        list_content = []
        list_company = []
        list_link = all_job_link
        list_datetime = all_job_datetime

        total = len(all_job_id)
        for i, job_id in enumerate(all_job_id):
        # for job_id in tqdm(all_job_id):
            try:
                company, jobTitle, jobDescription = self.get_job_details(job_id)
                list_title.append(jobTitle)
                list_content.append(jobDescription)
                list_company.append(company)
            except Exception as e:
                print(f"Failed to get job details for job_id {job_id}: {e}")
                continue

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


    def build_keywords(self):
        joined_keywords = " OR ".join([f'"{kw}"' for kw in self.keywords])
        return urllib.parse.quote(joined_keywords)



if __name__ == "__main__":
    job = Linkedin()
    df = job.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")

