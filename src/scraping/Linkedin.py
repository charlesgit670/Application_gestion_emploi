from tqdm import tqdm
import math
import time
import random
from bs4 import BeautifulSoup
import backoff
from requests.exceptions import RequestException, HTTPError

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time

class Linkedin(JobFinder):

    def __init__(self):
        self.url = 'https://www.linkedin.com/jobs/search?keywords=Data%20Scientist&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0'
        self.job_id_api = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=Data%20Scientist&location=Nanterre%2C%20%C3%8Ele-de-France%2C%20France&geoId=106218810&distance=5&f_JT=F&f_E=2%2C3%2C4&f_PP=102924436%2C103424094%2C106218810&f_TPR=r2592000&position=1&pageNum=0&start={}'
        self.job_description_api = 'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}'
    @measure_time
    def getJob(self):
        # Récupérer le nombre total d'offre
        res = self.get_content(self.url)
        soup = BeautifulSoup(res.text, 'html.parser')
        span = soup.find('span', class_='results-context-header__job-count')
        total_offer = int(span.get_text())

        # Récupérer tous les job id
        all_job_id = []
        all_job_link = []
        for i in range(0, math.ceil(total_offer / 10)):

            res = self.get_content(self.job_id_api.format(i * 10))
            soup = BeautifulSoup(res.text, 'html.parser')
            alljobs_on_this_page = soup.find_all("li")
            for job_on_this_page in alljobs_on_this_page:
                jobid = job_on_this_page.find("div", {"class": "base-card"}).get('data-entity-urn').split(":")[3]
                joblink = job_on_this_page.find("a")["href"]
                if jobid not in all_job_id:
                    all_job_id.append(jobid)
                    all_job_link.append(joblink)
        print(f"Nombre de fiche de poste Linkedin récupéré {len(all_job_id)}")

        # Récupérer le contenu de toutes les fiches de poste
        list_title = []
        list_content = []
        list_company = []
        list_link = all_job_link

        for job_id in tqdm(all_job_id):
            company, jobTitle, jobDescription = self.get_job_details(job_id)

            list_title.append(jobTitle)
            list_content.append(jobDescription)
            list_company.append(company)


        return self.formatData(list_title, list_content, list_company, list_link)

    @backoff.on_exception(backoff.expo, (HTTPError, RequestException), giveup=lambda e: e.response is not None and e.response.status_code != 429)
    def get_job_details(self, job_id):
        time.sleep(random.uniform(0.5, 2.0))
        resp = self.get_content(self.job_description_api.format(job_id))
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
    print(df)
