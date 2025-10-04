import json
import re
from bs4 import BeautifulSoup
import urllib.parse
import dateparser

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time


class ServicePublic(JobFinder):

    def __init__(self):
        self.get_config()

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url = re.sub(r'mot-cles/[^/]*', 'mot-cles/{}', config['url']['sp'])

    def build_keywords(self):
        joined_keywords = " ".join(self.keywords)
        return urllib.parse.quote(joined_keywords)

    def parse_date(self, date_to_parse):
        date_str = date_to_parse.replace("En ligne depuis le ", "").strip()
        date_obj = dateparser.parse(date_str, languages=["fr"])
        return date_obj.strftime("%Y-%m-%d")

    @measure_time
    def getJob(self, update_callback=None):
        keywords = self.build_keywords()
        url = self.url.format(keywords)

        # On récupère le nombre de page total à scrap
        res = self.get_content(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        try:
            pages = soup.select("ul.fr-pagination__list a.fr-pagination__link")
            page_numbers = [int(a.get_text(strip=True)) for a in pages if a.get_text(strip=True).isdigit()]
            last_page = max(page_numbers)
        except:
            last_page = 1


        # Stocker tous les jobs trouvés pour chaque page
        all_jobs = []
        for i in range(last_page):
            res = self.get_content(url + f"page/{i+1}")
            soup = BeautifulSoup(res.text, 'html.parser')
            offers = soup.select("div.fr-col-12.item")
            for offer in offers:
                job_link = offer.select_one("a.is-same-domain")["href"]
                job_title = offer.select_one("a.is-same-domain").get_text(strip=True)
                job_ministere = offer.select_one("img.fr-responsive-img").get("alt")
                job_datetime = self.parse_date(offer.select_one("li.fr-icon-calendar-line").get_text(strip=True))

                all_jobs.append((job_title, job_ministere, job_link, job_datetime))


        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste du Service Public récupéré {len(all_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []
        total = len(all_jobs)
        for i, (title, comp, link, datetime) in enumerate(all_jobs):
                res = self.get_content(link)
                soup = BeautifulSoup(res.text, 'html.parser')

                target_div = soup.find(
                    "div",
                    class_=lambda x: x is not None and "col-left" in x.split() and "rte" in x.split()
                )

                if not target_div:
                    # si la description n'est pas trouvée, on passe au job suivant
                    print(f"Aucune description trouvée pour {title}, passage au suivant.")
                    if update_callback:
                        update_callback(i + 1, total)
                    continue

                job_description = target_div.get_text(separator="\n", strip=True)

                list_title.append(title)
                list_content.append(job_description)
                list_company.append(comp)
                list_link.append(link)
                list_datetime.append(datetime)

                print(f"Service Public {i}/{total}")
                if update_callback:
                    update_callback(i + 1, total)


        df = self.formatData("sp", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df


if __name__ == "__main__":
    sp = ServicePublic()
    df = sp.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")
