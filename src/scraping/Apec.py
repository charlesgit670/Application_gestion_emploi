import json
import re
import threading
from datetime import datetime as dt, timedelta
# from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver, build_keyword_urls


class Apec(JobFinder):

    def __init__(self):
        self.get_config()
        # self.keywords = ["Data Scientist", "Machine Learning"]
        # self.url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={}&lieux=596212&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesContrat=101888&page=0&distance=15"
        self._thread_local = threading.local()
        self._drivers = []
        self._drivers_lock = threading.Lock()
        self._cookie_handled = False

    def _get_thread_driver(self):
        """Un seul driver Chrome par thread, réutilisé pour toutes les fiches qu'il traite."""
        driver = getattr(self._thread_local, "driver", None)
        if driver is None:
            driver = create_driver()
            self._thread_local.driver = driver
            with self._drivers_lock:
                self._drivers.append(driver)
        return driver

    def _quit_all_drivers(self):
        with self._drivers_lock:
            for driver in self._drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
            self._drivers = []

    def get_config(self):
        with open('config.json', 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.url_template = re.sub(r'motsCles=[^&]*', 'motsCles={keyword}', config['url']['apec'])
        self.keyword_mode = config.get("keyword_mode", {}).get("apec", "or")
        self.filter_day_scrap = int(config["filter_day_scrap"])

    def build_urls(self):
        return build_keyword_urls(
            base_url=self.url_template,
            keywords=self.keywords,
            mode=self.keyword_mode,
            encode_mode="query",
            quote_terms_for_or=True,
        )

    def scrape_job_detail(self, job_info, index, total):
        """Récupère le détail d'une fiche de poste via un driver réutilisé par thread."""
        title, comp, link, datetime = job_info
        driver = self._get_thread_driver()
        driver.get(link)
        job_description_element = WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='col-lg-8 border-L']"))
        )
        job_description = job_description_element.text
        print(f"APEC {index}/{total}")
        return (title, comp, link, datetime, job_description)



    @measure_time
    def getJob(self, update_callback=None):
        driver = create_driver()

        # Stocker tous les jobs trouvés
        all_jobs = []
        seen_links = set()
        count = 1
        list_title = []
        list_content = []
        list_company = []
        list_link = []
        list_datetime = []

        try:
            for url in self.build_urls():
                driver.get(url)
                count = 1

                while True:
                    print(f"Page {count}")

                    # Fermer la bannière de cookies si elle est présente (une seule fois : le
                    # consentement persiste ensuite pour toute la session du driver).
                    if not self._cookie_handled:
                        try:
                            cookie_banner = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.ID, "didomi-notice-disagree-button"))  # Refuser tous les cookies
                            )
                            # Permet de gérer les problemes en mode headless de bouton non cliquable
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cookie_banner)
                            cookie_banner = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.ID, "didomi-notice-disagree-button"))  # Refuser tous les cookies
                            )
                            cookie_banner.click()
                            print("Bannière de cookies fermée (refusé tous les cookies).")
                            # On ne marque comme géré qu'en cas de succès réel : si la bannière
                            # n'est pas encore apparue (chargement lent), on retente à la page suivante.
                            self._cookie_handled = True
                        except Exception:
                            # On n'affiche pas l'exception : le stacktrace natif de chromedriver
                            # (séquences d'adresses mémoire) polluerait inutilement les logs.
                            print("Aucune bannière de cookies détectée.")

                    # Attendre que l'élément contenant l'offre soit présent
                    offer_element = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[queryparamshandling='merge']"))
                    )

                    for offer in offer_element:
                        try:
                            job_link = offer.get_attribute("href")
                            if job_link in seen_links:
                                continue
                            seen_links.add(job_link)

                            job_title = offer.find_element(By.CSS_SELECTOR, "h2.card-title").text
                            company_name = offer.find_element(By.CSS_SELECTOR, "p.card-offer__company").text
                            datetime = offer.find_element(By.XPATH, ".//li[@title='Date de publication']").text
                        except StaleElementReferenceException:
                            # La carte a été ré-affichée par le site pendant la lecture (SPA) : on l'ignore,
                            # elle sera récupérée à la page suivante ou lors d'un prochain passage.
                            print("Carte d'offre obsolète (stale), ignorée.")
                            continue

                        # on filtre les offres trop ancienne
                        date_limit = dt.now() - timedelta(days=self.filter_day_scrap)
                        job_datetime_obj = dt.strptime(datetime, "%d/%m/%Y")

                        if job_title and company_name and job_link and job_datetime_obj >= date_limit:
                            all_jobs.append((job_title, company_name, job_link, datetime))

                    # Vérifier si un bouton "Page suivante" est actif
                    try:
                        all_items = driver.find_elements(By.CSS_SELECTOR, "ul.pagination li.page-item")
                        last = all_items[-1]
                        next_link = last.find_element(By.TAG_NAME, "a")
                        next_link.click()

                        print("Passage à la page suivante...")
                        count += 1
                    except Exception:
                        print("Fin de pagination")
                        break

            # Récupérer le contenu de toutes les fiches de poste en parallèle
            print(f"Nombre de fiche de poste APEC récupéré {len(all_jobs)}")
            total = len(all_jobs)
            max_workers = min(8, max(1, total))
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(self.scrape_job_detail, job, i, total): i
                        for i, job in enumerate(all_jobs)
                    }
                    for future in as_completed(futures):
                        try:
                            title, comp, link, datetime_str, job_description = future.result()
                            list_title.append(title)
                            list_content.append(job_description)
                            list_company.append(comp)
                            list_link.append(link)
                            list_datetime.append(datetime_str)
                            if update_callback:
                                update_callback(len(list_title), total)
                        except Exception as e:
                            print(f"Erreur lors de la récupération d'une fiche: {e}")
            finally:
                self._quit_all_drivers()

        finally:
            driver.quit()

        df = self.formatData("apec", list_title, list_content, list_company, list_link, list_datetime)
        df = df.drop_duplicates(subset="hash", keep="first")
        return df


if __name__ == "__main__":
    APC = Apec()
    df = APC.getJob()
    df = df.sort_values(by="date", ascending=False)
    print("a")
