from tqdm import tqdm
import pandas as pd
import json
import re
import math
import time
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

    def get_config(self):
        with open('config.json', 'r') as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url = re.sub(r'keywords=[^&]*', 'keywords={}', config['url']['linkedin'])
        self.job_id_api = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + self.url.split("search?")[1] + "&start={}"

    @measure_time
    def getJob(self, update_callback=None):
        # Récupérer le nombre total d'offre
        keywords = self.build_keywords()
        res = self.get_content(self.url.format(keywords))
        soup = BeautifulSoup(res.text, 'html.parser')
        span = soup.find('span', class_='results-context-header__job-count')
        total_offer = int(span.get_text())

        # Récupérer tous les job id
        all_job_id = []
        all_job_link = []
        all_job_datetime = []
        for i in range(0, math.ceil(total_offer / 10)):

            res = self.get_content(self.job_id_api.format(keywords, i * 10))
            soup = BeautifulSoup(res.text, 'html.parser')
            alljobs_on_this_page = soup.find_all("li")
            for job_on_this_page in alljobs_on_this_page:
                jobid = job_on_this_page.find("div", {"class": "base-card"})
                if jobid == None:
                    continue
                jobid = jobid.get('data-entity-urn').split(":")[3]
                joblink = job_on_this_page.find("a")["href"]
                jobDateTime = job_on_this_page.find("time")["datetime"]
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


    def build_keywords(self):
        joined_keywords = " OR ".join(self.keywords)
        return urllib.parse.quote(joined_keywords)



if __name__ == "__main__":
    job = Linkedin()
    df = job.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")

