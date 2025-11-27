# import pandas as pd
# from tqdm import tqdm
import time
# import os
import json
import re
from datetime import datetime as dt, timezone
# from dotenv import load_dotenv
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import urllib.parse

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver



class WelcomeToTheJungle(JobFinder):

    def __init__(self):
        # self.keywords = ["Data Scientist", "Machine Learning"]
        # self.url = "https://www.welcometothejungle.com/fr/jobs?refinementList%5Bcontract_type%5D%5B%5D=full_time&refinementList%5Bsectors.parent_reference%5D%5B%5D=industry-1&refinementList%5Bsectors.parent_reference%5D%5B%5D=public-administration-1&refinementList%5Bsectors.reference%5D%5B%5D=artificial-intelligence-machine-learning&refinementList%5Bsectors.reference%5D%5B%5D=big-data-1&refinementList%5Bsectors.reference%5D%5B%5D=cyber-security&refinementList%5Blanguage%5D%5B%5D=fr&refinementList%5Boffices.country_code%5D%5B%5D=FR&query={}&page=1&aroundQuery=Nanterre%2C%20France&searchTitle=false&aroundLatLng=48.88822%2C2.19428&aroundRadius=20"
        self.get_config()
    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url = re.sub(r'query=[^&]*', 'query={}', config['url']['wttj'])

    def build_urls(self):
        list_url = []
        for k in self.keywords:
            keyword = urllib.parse.quote(k)
            list_url.append(self.url.format(keyword))
        return list_url

    # def __login(self, driver):
    #     load_dotenv()
    #
    #     WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='not-logged-visible-login-button']"))
    #     ).click()
    #
    #     time.sleep(1)
    #
    #     # Remplir le champ email
    #     WebDriverWait(driver, 5).until(
    #         EC.presence_of_element_located((By.ID, "email_login"))
    #     ).send_keys(os.environ.get("EMAIL_WTTJ"))
    #
    #     # Remplir le champ mot de passe
    #     WebDriverWait(driver, 5).until(
    #         EC.presence_of_element_located((By.ID, "password"))
    #     ).send_keys(os.environ.get("PWD_WTTJ"))
    #
    #     # Soumettre le formulaire
    #     soumettre = WebDriverWait(driver, 5).until(
    #         EC.element_to_be_clickable((By.ID, "login-button-submit"))
    #     )
    #     # Scroll vers l'élément (important en headless)
    #     driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", soumettre)
    #
    #     WebDriverWait(driver, 5).until(
    #         EC.element_to_be_clickable((By.ID, "login-button-submit"))
    #     )
    #     soumettre.click()
    #
    #     print("✅ Connexion réussie.")

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

        try:
            btn = driver.find_element(By.XPATH, "//button[span[text()='Créer une alerte']]")
            driver.execute_script("arguments[0].style.display = 'none';", btn)
            print("Bouton alerte fermé.")
        except:
            print("Aucune bouton alterte détecté.")

    @measure_time
    def getJob(self, update_callback=None):
        driver = create_driver()
        list_urls = self.build_urls()

        # Stocker tous les jobs trouvés
        all_jobs = []
        for url in list_urls:
            driver.get(url)

            # self.__close_cookie_banner(driver)
            # self.__login(driver)

            count = 1
            while True:
                print(f"Page {count}")

                self.__close_cookie_banner(driver)

                job_cards = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//li[@data-testid='search-results-list-item-wrapper']"))
                )

                for card in job_cards:

                    # titre du job
                    title_elem = card.find_element(By.XPATH, ".//a[h2]")
                    title = title_elem.text.strip()
                    link = title_elem.get_attribute("href")

                    # nom de l’entreprise
                    company_elem = card.find_element(By.XPATH, ".//span[contains(concat(' ', normalize-space(@class), ' '), ' wui-text ')]")
                    company = company_elem.text.strip()

                    # gestion de la date ou du bouton "Sponsorisé"
                    try:
                        datetime = card.find_element(By.TAG_NAME, "time").get_attribute("datetime")
                    except NoSuchElementException:
                        datetime = dt.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                    if title and link and company and datetime:
                        all_jobs.append((title, company, link, datetime))


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

        # Elimination des doublons
        seen_links = set()
        unique_jobs = []

        for job in all_jobs:
            link = job[2]
            if link not in seen_links:
                unique_jobs.append(job)
                seen_links.add(link)
        # Récupérer le contenu de toutes les fiches de poste
        print(f"Nombre de fiche de poste WelcomeToTheJungle récupéré {len(unique_jobs)}")
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []
        total = len(unique_jobs)
        for i, (title, comp, link, datetime) in enumerate(unique_jobs):
        # for title, comp, link, datetime in tqdm(all_jobs):
            driver.get(link)

            for attempt in range(3):
                try:
                    voir_plus = WebDriverWait(driver, 3).until(
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
                    list_datetime.append(datetime)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"retrying... {attempt + 1}")
                        time.sleep(1)
                    else:
                        print(f"Failed to scrap")
                        print(link)
            print(f"WTTF {i}/{total}")
            if update_callback:
                update_callback(i + 1, total)

        driver.quit()

        df = self.formatData("wttj", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df




if __name__ == "__main__":
    WTJ = WelcomeToTheJungle()
    df = WTJ.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")

