# src/scraping/apec_scraper.py
import sys
import os
import json
import re
import time
import random
import urllib.parse
import pickle
from datetime import datetime as dt, timedelta
from playwright.sync_api import sync_playwright

# Ajouter le chemin src au sys.path pour pouvoir importer JobFinder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from JobFinder import JobFinder


def update_progress_file(project_root, current, total):
    """Écrit la progression dans un fichier JSON"""
    progress_file = os.path.join(project_root, 'data', 'apec_progress.json')
    os.makedirs(os.path.dirname(progress_file), exist_ok=True)
    with open(progress_file, 'w') as f:
        json.dump({'current': current, 'total': total}, f)


class ApecScraper(JobFinder):
    """Classe de scraping APEC qui hérite de JobFinder"""

    DETAIL_URL = "https://www.apec.fr/cms/webservices/offre/public"
    PAGE_SIZE = 20

    def __init__(self, project_root):
        self.project_root = project_root
        self._load_config()

    def _fetch_geo_coordinates(self, page):
        """Récupère les coordonnées GPS du lieu en interrogeant la première offre pivot APEC"""
        if not self.lieux:
            return

        lieu_param = str(self.lieux[0])

        try:
            geo_info = page.evaluate(f"""
                async () => {{
                    const lieuQuery = {json.dumps(lieu_param)};

                    // Payload minimal pour récupérer au moins 1 offre située dans le lieu cible
                    const payloadPivot = {{
                        "lieux": [lieuQuery],
                        "typeClient": "CADRE",
                        "sorts": [{{"type": "DATE", "direction": "DESCENDING"}}],
                        "pagination": {{"range": 1, "startIndex": 0}},
                        "activeFiltre": true,
                    }};

                    const response = await fetch('https://www.apec.fr/cms/webservices/rechercheOffre', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(payloadPivot)
                    }});

                    if (!response.ok) return null;

                    const data = await response.json();

                    // Extraction depuis le premier résultat de la liste
                    if (data.resultats && data.resultats.length > 0) {{
                        const premiereOffre = data.resultats[0];
                        if (premiereOffre.latitude && premiereOffre.longitude) {{
                            return {{
                                latitude: parseFloat(premiereOffre.latitude),
                                longitude: parseFloat(premiereOffre.longitude),
                            }};
                        }}
                    }}

                    return null;
                }}
            """)

            if geo_info:
                self.latitude = geo_info.get('latitude')
                self.longitude = geo_info.get('longitude')

                print(f"Coordonnées pivot récupérées via APEC -> Lat: {self.latitude}, Lon: {self.longitude}")
            else:
                print(f"⚠ Aucune offre trouvée pour extraire la géolocalisation de : {lieu_param}")

        except Exception as e:
            print(f"Erreur lors de la récupération des coordonnées pivot APEC : {e}")

    def _load_config(self):
        """Charge la configuration depuis config.json"""
        config_path = os.path.join(self.project_root, 'config.json')
        with open(config_path, 'r', encoding="utf-8") as f:
            config = json.load(f)

        self.keywords = config['keywords']
        self.keyword_mode = config.get("keyword_mode", {}).get("apec", "or")
        self.filter_day_scrap = int(config["filter_day_scrap"])

        # Parser l'URL
        parsed = urllib.parse.urlparse(config['url']['apec'])
        params = urllib.parse.parse_qs(parsed.query)

        self.lieux = [str(v) if v.isdigit() else v for v in params.get("lieux", [])]
        self.types_convention = [str(v) if v.isdigit() else v for v in params.get("typesConvention", [])]
        self.types_contrat = [str(v) if v.isdigit() else v for v in params.get("typesContrat", [])]
        distance_values = params.get("distance", ["0"])
        self.distance = int(distance_values[0]) if distance_values[0].isdigit() else 0
        self.latitude = None
        self.longitude = None

    def _build_payload(self, search_terms, start_index):
        """Construit le payload pour la recherche"""
        payload = {
            'lieux': self.lieux,
            'typeClient': 'CADRE',
            'sorts': [{'type': 'DATE', 'direction': 'DESCENDING'}],
            'pagination': {'range': self.PAGE_SIZE, 'startIndex': start_index},
            'activeFiltre': True,
            'motsCles': search_terms,
        }
        if self.types_contrat:
            payload['typesContrat'] = self.types_contrat
        if self.types_convention:
            payload['typesConvention'] = self.types_convention

        if self.distance > 0 and self.latitude and self.longitude:
            payload['pointGeolocDeReference'] = {
                'distance': str(self.distance),
                'latitude': self.latitude,
                'longitude': self.longitude,
            }
        return payload

    @staticmethod
    def _parse_date(raw_date):
        """Parse la date selon différents formats"""
        if raw_date is None:
            return None

        if isinstance(raw_date, (int, float)):
            return dt.fromtimestamp(raw_date / 1000)

        value = str(raw_date).strip()
        if value.isdigit():
            return dt.fromtimestamp(int(value) / 1000)

        for candidate, fmt in (
                (value[:19], "%Y-%m-%dT%H:%M:%S"),
                (value[:10], "%Y-%m-%d"),
                (value, "%d/%m/%Y"),
        ):
            try:
                return dt.strptime(candidate, fmt)
            except ValueError:
                continue
        return None

    def scrape(self):
        """Méthode principale de scraping"""

        # Construire les mots-clés
        if self.keyword_mode == "or":
            mots_cles_list = [' OR '.join([f'"{kw}"' for kw in self.keywords])]
        else:
            mots_cles_list = self.keywords

        all_jobs = []
        seen_links = set()
        date_limit = dt.now() - timedelta(days=self.filter_day_scrap)

        with sync_playwright() as p:
            browser = p.firefox.launch(
                headless=True,
                firefox_user_prefs={
                    'dom.webdriver.enabled': False,
                    'useAutomationExtension': False,
                }
            )

            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                viewport={'width': 1920, 'height': 1080},
                locale='fr-FR',
            )

            page = context.new_page()

            # Masquer la détection
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Initialiser la session
            print("Initialisation...")
            page.goto("https://www.apec.fr/", wait_until='networkidle')
            time.sleep(3)

            # Attendre la résolution du captcha si nécessaire
            try:
                page.wait_for_function("""
                    () => !document.body.innerText.includes('Please enable JS')
                """, timeout=20000)
                print("Session initialisée")
            except:
                print("Pas de captcha ou déjà résolu")

            # Récupération des coordonnées géographiques
            self._fetch_geo_coordinates(page)

            # Recherche
            for search_terms in mots_cles_list:
                start_index = 0
                while True:
                    payload = self._build_payload(search_terms, start_index)

                    try:
                        response = page.evaluate("""
                            async (data) => {
                                const response = await fetch('https://www.apec.fr/cms/webservices/rechercheOffre', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json;charset=UTF-8',
                                        'Accept': 'application/json, text/plain, */*',
                                    },
                                    body: JSON.stringify(data),
                                    credentials: 'include'
                                });
                                if (response.ok) {
                                    return await response.json();
                                }
                                return null;
                            }
                        """, payload)
                    except Exception as e:
                        print(f"Erreur recherche: {e}")
                        response = None

                    if response is None:
                        break

                    page_results = response.get('resultats', [])

                    if not page_results:
                        break

                    print(f"APEC recherche startIndex={start_index} -> {len(page_results)} offres")

                    reached_date_limit = False
                    for result in page_results:
                        job_datetime_obj = self._parse_date(result.get('datePublication'))
                        if job_datetime_obj is None:
                            continue
                        if job_datetime_obj < date_limit:
                            reached_date_limit = True
                            break

                        numero_offre = result.get('numeroOffre')
                        job_title = result.get('intitule')
                        company_name = result.get('nomCommercial')
                        if not (numero_offre and job_title and company_name):
                            continue

                        link = 'https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/' + numero_offre
                        if link in seen_links:
                            continue

                        seen_links.add(link)
                        all_jobs.append({
                            'numeroOffre': numero_offre,
                            'title': job_title,
                            'company': company_name,
                            'link': link,
                            'date': job_datetime_obj.strftime("%d/%m/%Y"),
                        })

                    if reached_date_limit:
                        print(f"Limite de {self.filter_day_scrap} jours atteinte, arrêt de la pagination.")
                        break

                    if len(page_results) < self.PAGE_SIZE:
                        break

                    start_index += self.PAGE_SIZE
                    time.sleep(random.uniform(0.5, 1.0))

            print(f"Nombre de fiche de poste APEC récupéré {len(all_jobs)}")
            total = len(all_jobs)

            list_title, list_content, list_company, list_link, list_datetime = [], [], [], [], []

            # Compteur d'échecs consécutifs
            consecutive_failures = 0
            RESET_INTERVAL = 50

            # Scraping des détails
            for i, job in enumerate(all_jobs):
                try:
                    # Réinitialiser la session toutes les 50 offres
                    if i > 0 and i % RESET_INTERVAL == 0:
                        print(f"\n⚠ Réinitialisation de la session après {i} offres...")
                        page.goto("https://www.apec.fr/", wait_until='networkidle')
                        time.sleep(5)

                        try:
                            page.wait_for_function("""
                                () => !document.body.innerText.includes('Please enable JS')
                            """, timeout=30000)
                            print("✓ Session réinitialisée")
                        except:
                            print("⚠ Impossible de réinitialiser la session")

                        time.sleep(3)
                        consecutive_failures = 0

                    # Mettre à jour la progression
                    update_progress_file(self.project_root, i, total)

                    print(f"APEC {i + 1}/{total}")

                    url = f"{self.DETAIL_URL}?numeroOffre={job['numeroOffre']}"
                    page.goto(url, wait_until='domcontentloaded')

                    try:
                        page.wait_for_function("""
                            () => {
                                const body = document.body.innerText;
                                return !body.includes('Please enable JS') && body.length > 0;
                            }
                        """, timeout=15000)
                    except:
                        pass

                    content = page.evaluate("() => document.body.innerText")

                    # Vérifier si on a un captcha
                    if "Please enable JS" in content or "captcha" in content.lower():
                        print(f"⚠ Captcha détecté, attente de résolution...")
                        try:
                            page.wait_for_function("""
                                () => {
                                    const body = document.body.innerText;
                                    return !body.includes('Please enable JS') && body.length > 0;
                                }
                            """, timeout=60000)
                            content = page.evaluate("() => document.body.innerText")
                            consecutive_failures = 0
                        except:
                            print(f"✗ Timeout captcha pour {job['numeroOffre']}")
                            consecutive_failures += 1
                            time.sleep(5)
                            continue

                    try:
                        detail = json.loads(content)
                        consecutive_failures = 0
                    except:
                        detail = None
                        consecutive_failures += 1

                    if detail is None:
                        print(f"Échec pour {job['numeroOffre']} (échecs consécutifs: {consecutive_failures})")

                        if consecutive_failures >= 3:
                            print(f"⚠ Trop d'échecs consécutifs, réinitialisation de la session...")
                            page.goto("https://www.apec.fr/", wait_until='networkidle')
                            time.sleep(5)

                            try:
                                page.wait_for_function("""
                                    () => !document.body.innerText.includes('Please enable JS')
                                """, timeout=30000)
                                print("✓ Session réinitialisée")
                            except:
                                print("⚠ Impossible de réinitialiser la session")

                            time.sleep(3)
                            consecutive_failures = 0

                        continue

                    parts = [
                        detail.get("texteHtml") or "",
                        detail.get("texteHtmlEntreprise") or "",
                        detail.get("texteHtmlProfil") or "",
                    ]
                    job_description = "\n\n".join(p for p in parts if p)
                    job_description = re.sub(r"<[^>]+>", " ", job_description)
                    job_description = re.sub(r"&nbsp;", " ", job_description)
                    job_description = re.sub(r"\s+", " ", job_description).strip()

                    list_title.append(job['title'])
                    list_content.append(job_description)
                    list_company.append(job['company'])
                    list_link.append(job['link'])
                    list_datetime.append(job['date'])

                    # Mettre à jour la progression après succès
                    update_progress_file(self.project_root, i + 1, total)

                except Exception as e:
                    print(f"Erreur lors de la récupération d'une fiche: {e}")
                    consecutive_failures += 1

                    if consecutive_failures >= 3:
                        print(f"⚠ Réinitialisation après {consecutive_failures} erreurs...")
                        page.goto("https://www.apec.fr/", wait_until='networkidle')
                        time.sleep(5)
                        consecutive_failures = 0
                    else:
                        time.sleep(3)

            # Progression finale
            update_progress_file(self.project_root, total, total)

            browser.close()

        # Utiliser formatData hérité de JobFinder
        df = self.formatData(
            "apec",
            list_title,
            list_content,
            list_company,
            list_link,
            list_datetime
        )
        df = df.drop_duplicates(subset="hash", keep="first")

        # Sauvegarder en pickle
        data_dir = os.path.join(self.project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        output_file = os.path.join(data_dir, 'apec_result.pkl')

        with open(output_file, 'wb') as f:
            pickle.dump(df, f)


        print(f"\nAPEC terminé: {len(df)}/{total} offres scrapées avec succès")
        return len(df)


def scrape_apec():
    """Fonction principale appelée par le process séparé"""
    # Déterminer la racine du projet
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Créer le scraper et lancer le scraping
    scraper = ApecScraper(project_root)
    return scraper.scrape()


if __name__ == "__main__":
    count = scrape_apec()
    print(f"RESULT_COUNT:{count}")