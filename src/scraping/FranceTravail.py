import json
import re
import time

from bs4 import BeautifulSoup
import urllib.parse
import dateparser
from datetime import datetime, timedelta
import re

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time


class FranceTravail(JobFinder):

    def __init__(self):
        self.get_config()

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url = re.sub(r'([?&])range=[^&]*(&|$)', r'\1', re.sub(r'motsCles=[^&]*', 'motsCles={}', config['url']['ft'])).rstrip('&')
        self.filter_day_scrap = int(config["filter_day_scrap"])

    def build_urls(self):
        urls = []
        for k in self.keywords:
            keyword = "+".join(k.split())
            urls.append(self.url.format(keyword))
        return urls

    def parse_date(self, date_str):
        now = datetime.now()
        date_str = date_str.lower()

        # Cas : "Publié aujourd'hui"
        if "aujourd'hui" in date_str:
            return now

        # Cas : "Publié hier"
        if "hier" in date_str:
            return now - timedelta(days=int(1))

        # Cas : "il y a X jours"
        if 'jour' in date_str:
            days_ago = re.search(r'(\d+)', date_str)
            if days_ago:
                return now - timedelta(days=int(days_ago.group(1)))

        return now

    @measure_time
    def getJob(self, update_callback=None):
        urls = self.build_urls()
        all_jobs = []
        for url in urls:
            # On récupère le nombre d'offres total
            res = self.get_content(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            h1_title = soup.select('h1.title')
            if not h1_title:
                continue
            total_offer = h1_title[0].get_text(strip=True).split()[0]

            if total_offer.isdigit():
                total_offer = int(total_offer)
            else:
                continue

            for i in range(0, total_offer, 20):
                res = self.get_content(url + f"&range={i}-{i+19}")
                soup = BeautifulSoup(res.text, 'html.parser')
                result_list = soup.find('ul', {'class': 'result-list'})
                if not result_list:
                    continue
                offers = result_list.find_all('li', recursive=False)

                for num, offer in enumerate(offers):
                    offer_content = offer.find('a', attrs={"class": "media with-fav"})
                    if not offer_content:
                        continue
                    job_link = "https://candidat.francetravail.fr" + offer_content.get('href', '')
                    title_elem = offer_content.select('div.media-body h2')
                    company_elem = offer_content.select('div.media-body p.subtext')
                    date_elem = offer_content.select('div.media-body p.date')
                    if not title_elem or not company_elem or not date_elem:
                        continue
                    job_title = title_elem[0].get_text()
                    job_company = company_elem[0].get_text()
                    job_datetime = self.parse_date(date_elem[0].get_text(strip=True))

                    date_limit = datetime.now() - timedelta(days=self.filter_day_scrap)
                    if job_title and job_link and job_company and job_datetime >= date_limit:
                        all_jobs.append((job_title, job_company, job_link, job_datetime))

        # Elimination des doublons
        seen_links = set()
        unique_jobs = []

        for job in all_jobs:
            link = job[2]
            if link not in seen_links:
                unique_jobs.append(job)
                seen_links.add(link)

        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste France Travail récupéré {len(unique_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []
        total = len(unique_jobs)
        for i, (title, comp, link, date) in enumerate(unique_jobs):
            for attempt in range(3):
                try:
                    res = self.get_content(link)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    description_elem = soup.find('div', attrs={"class": "description"})
                    if not description_elem:
                        continue
                    job_description = description_elem.get_text(strip=True, separator='\n')

                    list_title.append(title)
                    list_content.append(job_description)
                    list_company.append(comp)
                    list_link.append(link)
                    list_datetime.append(date)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"retrying... {attempt + 1}")
                        time.sleep(1)
                    else:
                        print(f"Failed to scrap")
                        print(link)

            print(f"France Travail {i}/{total}")
            if update_callback:
                update_callback(i + 1, total)

        df = self.formatData("ft", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df

if __name__ == "__main__":
    hw = FranceTravail()
    df = hw.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")