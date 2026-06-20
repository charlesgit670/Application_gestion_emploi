import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, build_keyword_urls


class HelloWork(JobFinder):

    def __init__(self):
        self.get_config()

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url_template = re.sub(r'k=[^&]*', 'k={keyword}', config['url']['hw'])
        self.keyword_mode = config.get("keyword_mode", {}).get("hw", "one_by_one")
        self.filter_day_scrap = int(config["filter_day_scrap"])

    def build_urls(self):
        return build_keyword_urls(
            base_url=self.url_template,
            keywords=self.keywords,
            mode=self.keyword_mode,
            encode_mode="query",
            quote_terms_for_or=False,
        )

    def parse_date(self, date_str):
        now = datetime.now()
        date_str = date_str.lower()

        # Cas : "il y a X heures" ou "moins de X heures"
        if 'heure' in date_str:
            return now

        # Cas : "il y a X jours"
        if 'jour' in date_str:
            days_ago = re.search(r'(\d+)', date_str)
            if days_ago:
                return now - timedelta(days=int(days_ago.group(1)))

        # Cas : "il y a X mois" ou "plus de 1 mois"
        if 'mois' in date_str:
            months_ago = re.search(r'(\d+)', date_str)
            count = int(months_ago.group(1)) if months_ago else 1
            return now - timedelta(days=count * 30)

        return now

    @measure_time
    def getJob(self, update_callback=None):
        urls = self.build_urls()
        all_jobs = []
        for url in urls:
            try:
            # On récupère le nombre de page total à scrap
                res = self.get_content(url)
                soup = BeautifulSoup(res.text, 'html.parser')
                try:
                    # pages = soup.select('nav[class*="tw-flex"] button[name="p"]')
                    # page_numbers = [int(a.get_text(strip=True)) for a in pages if a.get_text(strip=True).isdigit()]
                    # last_page = max(page_numbers)

                    pages = soup.select('nav.sm\\:flex button[name="p"]')
                    page_numbers = [int(btn.get_text(strip=True)) for btn in pages if btn.get_text(strip=True).isdigit()]
                    last_page = max(page_numbers) if page_numbers else 1
                except:
                    last_page = 1

                # Stocker tous les jobs trouvés pour chaque page
                for i in range(last_page):
                    res = self.get_content(url + f"&p={i + 1}")
                    soup = BeautifulSoup(res.text, 'html.parser')
                    offers = soup.find('ul', {'aria-label': 'liste des offres'}).find_all('li', recursive=False)
                    for num, offer in enumerate(offers):
                        offer_content = offer.find('a', attrs={"data-cy": "offerTitle"})
                        job_link = "https://www.hellowork.com" + offer_content.get('href', '')
                        paragraphs = offer_content.find('h3').find_all('p')
                        job_title = paragraphs[0].get_text(strip=True)
                        job_company = paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else "Non spécifié"
                        job_datetime = self.parse_date(offer.find('div', class_='text-grey-500').get_text(strip=True))

                        date_limit = datetime.now() - timedelta(days=self.filter_day_scrap)
                        if job_title and job_link and job_company and job_datetime >= date_limit:
                            all_jobs.append((job_title, job_company, job_link, job_datetime))
            except:
                print("Pas d'offres trouvés : ", url)


        # Elimination des doublons
        seen_links = set()
        unique_jobs = []

        for job in all_jobs:
            link = job[2]
            if link not in seen_links:
                unique_jobs.append(job)
                seen_links.add(link)

        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste HelloWork récupéré {len(unique_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []
        total = len(unique_jobs)
        for i, (title, comp, link, date) in enumerate(unique_jobs):
            res = self.get_content(link)
            soup = BeautifulSoup(res.text, 'html.parser')

            description_div = soup.find('div', attrs={"data-truncate-text-target": "content"})
            if not description_div:
                print(f"Aucune description trouvée pour {title}, passage au suivant.")
                if update_callback:
                    update_callback(i + 1, total)
                continue

            job_description = description_div.get_text(strip=True, separator='\n')

            list_title.append(title)
            list_content.append(job_description)
            list_company.append(comp)
            list_link.append(link)
            list_datetime.append(date)

            print(f"HelloWork {i}/{total}")
            if update_callback:
                update_callback(i + 1, total)

        df = self.formatData("hw", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df

if __name__ == "__main__":
    hw = HelloWork()
    df = hw.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")