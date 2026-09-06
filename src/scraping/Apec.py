# src/scraping/Apec.py
import json
import subprocess
import sys
import os
import pickle
import urllib.parse
import time
from datetime import datetime as dt, timedelta
from scraping.JobFinder import JobFinder
from scraping.utils import measure_time


class Apec(JobFinder):
    SEARCH_URL = "https://www.apec.fr/cms/webservices/rechercheOffre"
    DETAIL_URL = "https://www.apec.fr/cms/webservices/offre/public"
    PAGE_SIZE = 20

    def __init__(self):
        self.get_config()

    def get_config(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, 'config.json')

        with open(config_path, 'r', encoding="utf-8") as f:
            config = json.load(f)
        self.keywords = config['keywords']
        self.keyword_mode = config.get("keyword_mode", {}).get("apec", "or")
        self.filter_day_scrap = int(config["filter_day_scrap"])
        self._parse_search_url(config['url']['apec'])

    def _parse_search_url(self, url):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.lieux = [int(v) if v.isdigit() else v for v in params.get("lieux", [])]
        self.types_convention = [int(v) if v.isdigit() else v for v in params.get("typesConvention", [])]
        self.types_contrat = [int(v) if v.isdigit() else v for v in params.get("typesContrat", [])]
        distance_values = params.get("distance", ["0"])
        self.distance = int(distance_values[0]) if distance_values[0].isdigit() else 0

    @measure_time
    def getJob(self, update_callback=None):
        """Exécute APEC dans un process séparé avec sync_playwright"""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apec_scraper.py')
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        if not os.path.exists(script_path):
            raise Exception(f"Script introuvable: {script_path}")

        print("Lancement du process APEC...")

        # Démarrer le process SANS rediriger la sortie
        # Les print() du process enfant iront directement dans la console parente
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=project_root,
            # Pas de redirection : la sortie va directement dans la console
            stdout=None,  # Hérite de la console parente
            stderr=None,  # Hérite de la console parente
        )

        # Surveiller la progression pendant que le process s'exécute
        progress_file = os.path.join(project_root, 'data', 'apec_progress.json')

        while process.poll() is None:
            if update_callback and os.path.exists(progress_file):
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                    current = progress.get('current', 0)
                    total = progress.get('total', 1)
                    update_callback(current, max(total, 1))
                except:
                    pass
            time.sleep(0.5)

        if process.returncode != 0:
            raise Exception(f"Process APEC a échoué avec le code {process.returncode}")

        output_file = os.path.join(project_root, 'data', 'apec_result.pkl')

        if not os.path.exists(output_file):
            raise Exception(f"Aucun résultat APEC trouvé dans {output_file}")

        with open(output_file, 'rb') as f:
            df = pickle.load(f)

        os.remove(output_file)

        total = len(df)
        if update_callback:
            update_callback(total, total)

        return df