from tqdm import tqdm
import time
import os
from dotenv import load_dotenv
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver



class WelcomeToTheJungle(JobFinder):

    def __init__(self):
        # super().__init__(job_title, contract)
        self.url = "https://www.welcometothejungle.com/fr/jobs?refinementList%5Bcontract_type%5D%5B%5D=full_time&refinementList%5Bsectors.parent_reference%5D%5B%5D=industry-1&refinementList%5Bsectors.parent_reference%5D%5B%5D=public-administration-1&refinementList%5Bsectors.reference%5D%5B%5D=artificial-intelligence-machine-learning&refinementList%5Bsectors.reference%5D%5B%5D=big-data-1&refinementList%5Bsectors.reference%5D%5B%5D=cyber-security&refinementList%5Blanguage%5D%5B%5D=fr&refinementList%5Boffices.country_code%5D%5B%5D=FR&query=data%20scientist&page=1&aroundQuery=Nanterre%2C%20France&searchTitle=false&aroundLatLng=48.88822%2C2.19428&aroundRadius=20"
    def __login(self, driver):
        load_dotenv()

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='not-logged-visible-login-button']"))
        ).click()

        # Remplir le champ email
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "email_login"))
        ).send_keys(os.environ.get("EMAIL_WTTJ"))

        # Remplir le champ mot de passe
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "password"))
        ).send_keys(os.environ.get("PWD_WTTJ"))

        # Soumettre le formulaire
        soumettre = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "login-button-submit"))
        )
        # Scroll vers l'élément (important en headless)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", soumettre)

        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "login-button-submit"))
        )
        soumettre.click()

        print("✅ Connexion réussie.")

    def __close_cookie_banner(self, driver):
        # Fermer la bannière de cookies si elle est présente
        try:
            cookie_banner = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.ID, "axeptio_btn_dismiss"))  # Refuser tous les cookies
            )
            cookie_banner.click()
            print("Bannière de cookies fermée (refusé tous les cookies).")
        except:
            print("Aucune bannière de cookies détectée.")

    @measure_time
    def getJob(self):
        driver = create_driver()
        driver.get(self.url)

        self.__close_cookie_banner(driver)
        self.__login(driver)

        # Stocker tous les jobs trouvés
        all_jobs = []
        count = 1
        while True:
            print(f"Page {count}")

            self.__close_cookie_banner(driver)

            job_elements = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[@class='sc-flttKd hSdoDt']//a"))
            )

            job_company = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.XPATH, "//span[@class='sc-izXThL fFdRYJ sc-bMgOzA bJPygT wui-text']"))
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
                    EC.element_to_be_clickable((By.XPATH, '//nav[@aria-label="Pagination"]//li[last()]//a'))
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
        print(f"Nombre de fiche de poste WelcomeToTheJungle récupéré {len(all_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        for title, comp, link in tqdm(all_jobs):
            driver.get(link)

            for attempt in range(3):
                try:
                    voir_plus = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Voir plus')]"))
                    )

                    # Scroll vers l'élément (important en headless)
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", voir_plus)

                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Voir plus')]"))
                    )

                    voir_plus.click()

                    description_div = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@id='the-position-section']"))
                    )

                    # Récupérer le texte
                    job_description = description_div.text
                    list_title.append(title)
                    list_content.append(job_description)
                    list_company.append(comp)
                    list_link.append(link)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"retrying... {attempt + 1}")
                        time.sleep(1)
                    else:
                        print(f"Failed to scrap")
                        print(link)
        driver.quit()



        return self.formatData(list_title, list_content, list_company, list_link)




if __name__ == "__main__":
    WTJ = WelcomeToTheJungle()
    df = WTJ.getJob()

