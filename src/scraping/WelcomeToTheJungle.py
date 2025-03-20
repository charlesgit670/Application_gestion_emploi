# from bs4 import BeautifulSoup
# import json
from tqdm import tqdm
# import multiprocessing
# import concurrent.futures
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver



class WelcomeToTheJungle(JobFinder):

    def __init__(self):
        # super().__init__(job_title, contract)
        self.url = "https://www.welcometothejungle.com/fr/jobs?refinementList%5Bcontract_type%5D%5B%5D=full_time&refinementList%5Bsectors.parent_reference%5D%5B%5D=industry-1&refinementList%5Bsectors.parent_reference%5D%5B%5D=public-administration-1&refinementList%5Bsectors.reference%5D%5B%5D=artificial-intelligence-machine-learning&refinementList%5Bsectors.reference%5D%5B%5D=big-data-1&refinementList%5Bsectors.reference%5D%5B%5D=cyber-security&refinementList%5Blanguage%5D%5B%5D=fr&refinementList%5Boffices.country_code%5D%5B%5D=FR&query=data%20scientist&page=1&aroundQuery=Nanterre%2C%20France&searchTitle=false&aroundLatLng=48.88822%2C2.19428&aroundRadius=10"

    @measure_time
    def getJob(self):
        driver = create_driver()
        driver.get(self.url)

        # Stocker tous les jobs trouvés
        all_jobs = []
        count = 1
        while True:
            print(f"Page {count}")
            job_elements = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[@class='sc-gVcfYu bkUuhH']//a"))
            )

            job_company = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.XPATH, "//span[@class='sc-lizKOf LGoxu sc-eRdibt hPAZrU wui-text']"))
            )

            for job, comp in zip(job_elements, job_company):
                title = job.text
                link = job.get_attribute('href')
                company = comp.text
                if title and link:
                    all_jobs.append((title, company, link))

            # Vérifier si un bouton "Page suivante" est actif
            try:
                next_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, "//ul[@class='sc-fCmSaK dyOVxg']//li[last()]//a"))
                )
                is_disabled = next_button.get_attribute("aria-disabled")

                if is_disabled == "false":
                    print("Passage à la page suivante...")
                    count += 1
                    next_button.click()
                else:
                    print("Fin de pagination")
                    break
            except TimeoutException:
                print("Fin de pagination")
                break



        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste récupéré {len(all_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        for title, comp, link in tqdm(all_jobs):
            driver.get(link)

            voir_plus_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Voir plus')]"))
            )
            voir_plus_button.click()

            description_div = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='sc-bXCLTC eCbjRu sc-cVOTOZ hxoGKK']"))
            )

            # Récupérer le texte
            job_description = description_div.text
            list_title.append(title)
            list_content.append(job_description)
            list_company.append(comp)
            list_link.append(link)

        # # Fonction globale pour scraper les détails du job
        # def scrape_job_details(title, link):
        #     driver = create_driver()
        #     driver.get(link)
        #
        #     try:
        #         # Cliquer sur le bouton 'Voir plus'
        #         voir_plus_button = WebDriverWait(driver, 10).until(
        #             EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Voir plus')]"))
        #         )
        #         voir_plus_button.click()
        #
        #         # Récupérer la description du job
        #         description_div = WebDriverWait(driver, 10).until(
        #             EC.presence_of_element_located((By.XPATH, "//div[@data-testid='job-section-description']"))
        #         )
        #         job_description = description_div.text
        #
        #         return title, job_description, link
        #
        #     except Exception as e:
        #         print(f"Error processing {title}: {str(e)}")
        #         return None
        #
        #     finally:
        #         driver.quit()
        #
        # # Récupérer le contenu de toutes les fiches de poste
        # print(f"Nombre de fiche de poste récupéré {len(all_jobs)}")
        # list_title = []
        # list_content = []
        # list_link = []

        # # Lancer les threads pour chaque travail à scraper
        # with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        #     futures = [executor.submit(scrape_job_details, title, link) for title, link in all_jobs]
        #
        #     # Attendre les résultats des threads
        #     for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Scraping jobs"):
        #         result = future.result()
        #         if result:
        #             title, job_description, link = result
        #             list_title.append(title)
        #             list_content.append(job_description)
        #             list_link.append(link)

        # Fermer le navigateur
        driver.quit()



        return self.formatData(list_title, list_content, list_company, list_link)




if __name__ == "__main__":
    WTJ = WelcomeToTheJungle()
    df = WTJ.getJob()

