import pandas as pd
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver


class Apec(JobFinder):

    def __init__(self):
        self.keywords = ["Data Scientist", "Machine Learning"]
        self.url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={}&lieux=596212&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesContrat=101888&page=0&distance=15"

    def build_keywords(self):
        joined_keywords = " OR ".join(self.keywords)
        return urllib.parse.quote(joined_keywords)

    def formatData(self, list_title, list_content, list_company, list_link, list_datetime):
        data = {
            "title": list_title,
            "content": list_content,
            "company": list_company,
            "link": list_link,
            "date": list_datetime,
            "is_read": 0,
            "is_apply": 0,
            "is_refused": 0,
            "is_good_offer": 1,
            "comment": "",
            "score": 0,
            "custom_profile": ""
        }
        df = pd.DataFrame(data=data)
        df["date"] = pd.to_datetime(df["date"], dayfirst=True).dt.date
        return df


    @measure_time
    def getJob(self, update_callback=None):
        driver = create_driver()
        keyword = self.build_keywords()
        driver.get(self.url.format(keyword))

        # Stocker tous les jobs trouvés
        all_jobs = []
        count = 1
        while True:
            print(f"Page {count}")

            # Fermer la bannière de cookies si elle est présente
            try:
                cookie_banner = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))  # Refuser tous les cookies
                )
                # Permet de gérer les problemes en mode headless de bouton non cliquable
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cookie_banner)
                cookie_banner = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))  # Refuser tous les cookies
                )
                cookie_banner.click()
                print("Bannière de cookies fermée (refusé tous les cookies).")
            except Exception as e:
                print(e)
                print("Aucune bannière de cookies détectée.")

            # Attendre que l'élément contenant l'offre soit présent
            offer_element = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[queryparamshandling='merge']"))
            )

            for offer in offer_element:
                job_link = offer.get_attribute("href")
                job_title = offer.find_element(By.CSS_SELECTOR, "h2.card-title").text
                company_name = offer.find_element(By.CSS_SELECTOR, "p.card-offer__company").text
                datetime = offer.find_element(By.XPATH, ".//li[@title='Date de publication']").text

                if job_title and company_name and job_link:
                    all_jobs.append((job_title, company_name, job_link, datetime))

            # Vérifier si un bouton "Page suivante" est actif
            try:
                next_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "li.page-item.next a.page-link"))
                )
                next_button.click()
                print("Passage à la page suivante...")
                count += 1
            except Exception as e:
                print("Fin de pagination")
                # print(e)
                break

        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste APEC récupéré {len(all_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []
        total = len(all_jobs)
        for i, (title, comp, link, datetime) in enumerate(all_jobs):
        # for title, comp, link, datetime in tqdm(all_jobs):
            driver.get(link)

            job_description_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='col-lg-8 border-L']"))
            )

            job_description = job_description_element.text

            list_title.append(title)
            list_content.append(job_description)
            list_company.append(comp)
            list_link.append(link)
            list_datetime.append(datetime)

            print(f"APEC {i}/{total}")
            if update_callback:
                update_callback(i + 1, total)

        driver.quit()

        return self.formatData(list_title, list_content, list_company, list_link, list_datetime)


if __name__ == "__main__":
    APC = Apec()
    df = APC.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")
