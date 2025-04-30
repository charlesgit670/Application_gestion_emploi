import pandas as pd
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver


class Apec(JobFinder):

    def __init__(self):
        self.url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=data%20scientist&lieux=596212&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesContrat=101888&page=0&distance=15"
    @measure_time
    def getJob(self):
        driver = create_driver()
        driver.get(self.url)

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
                cookie_banner.click()
                print("Bannière de cookies fermée (refusé tous les cookies).")
            except:
                print("Aucune bannière de cookies détectée.")

            # Attendre que l'élément contenant l'offre soit présent
            offer_element = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[queryparamshandling='merge']"))
            )

            for offer in offer_element:
                job_link = offer.get_attribute("href")
                job_title = offer.find_element(By.CSS_SELECTOR, "h2.card-title").text
                company_name = offer.find_element(By.CSS_SELECTOR, "p.card-offer__company").text

                if job_title and company_name and job_link:
                    all_jobs.append((job_title, company_name, job_link))

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
        for title, comp, link in tqdm(all_jobs):
            driver.get(link)

            job_description_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='col-lg-8 border-L']"))
            )

            job_description = job_description_element.text

            list_title.append(title)
            list_content.append(job_description)
            list_company.append(comp)
            list_link.append(link)

        driver.quit()

        return self.formatData(list_title, list_content, list_company, list_link)


if __name__ == "__main__":
    APC = Apec()
    df = APC.getJob()
    print("a")
