import pandas as pd
import os
import json
import time
# from rapidfuzz import fuzz
from datetime import datetime
import shutil
# from dotenv import load_dotenv
from openai import OpenAI
from mistralai import Mistral
from tqdm import tqdm
from enum import Enum

from scraping.FranceTravail import FranceTravail
from scraping.HelloWork import HelloWork
from scraping.WelcomeToTheJungle import WelcomeToTheJungle
from scraping.Apec import Apec
from scraping.Linkedin import Linkedin
from scraping.ServicePublic import ServicePublic
from scraping.utils import measure_time, add_LLM_comment, is_language_allowed
from concurrent.futures import ThreadPoolExecutor, as_completed


class Platform(Enum):
    wttj = WelcomeToTheJungle
    apec = Apec
    linkedin = Linkedin
    sp = ServicePublic
    hw = HelloWork
    ft = FranceTravail

def get_all_job(progress_dict, all_platforms, is_multiproc):

    def run_source(source_class):
        name = source_class.__name__
        platform = source_class()
        callback_state = {'total': 0}

        def update_callback(current, total):
            callback_state['total'] = total
            progress_dict[name] = (current, total)

        try:
            result = platform.getJob(update_callback=update_callback)
            # Garantir l'état terminal après scraping réussi
            if callback_state['total'] > 0:
                progress_dict[name] = (callback_state['total'], callback_state['total'])
            return result
        except Exception as e:
            # État terminal en cas d'erreur : (1, 1)
            progress_dict[name] = (1, 1)
            raise

    if is_multiproc:
        results = []
        with ThreadPoolExecutor(max_workers=len(all_platforms)) as executor:
            # submit + as_completed plutôt que executor.map() :
            # avec map(), une exception dans un thread est re-levée et annule
            # tous les résultats déjà collectés. Ici chaque scraper est isolé.
            futures = {executor.submit(run_source, cls): cls for cls in all_platforms}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"Erreur lors du scraping de {futures[future].__name__}: {e}")
    else:
        results = []
        for cls in all_platforms:
            try:
                results.append(run_source(cls))
            except Exception as e:
                print(f"Erreur lors du scraping de {cls.__name__}: {e}")

    # Guard : si tous les scrapers ont échoué, pd.concat([]) lèverait une ValueError.
    if not results:
        return pd.DataFrame()
    return pd.concat(results)




def get_store_data():
    file_path = "data/job.csv"
    backup_dir = "data/backup/"

    if os.path.exists(file_path):
        # Créer le dossier de backup s'il n'existe pas
        os.makedirs(backup_dir, exist_ok=True)

        # Générer un nom de fichier avec date et heure
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(backup_dir, f"job_backup_{timestamp}.csv")

        # Copier le fichier
        shutil.copy(file_path, backup_file)
        print(f"Backup créé : {backup_file}")
        return pd.read_csv(file_path, sep=";", encoding="utf-8")
    else:
        return pd.DataFrame(columns=["title",
                                     "content",
                                     "company",
                                     "link",
                                     "date",
                                     "is_read",
                                     "is_apply",
                                     "is_refused",
                                     "is_good_offer",
                                     "comment",
                                     "score",
                                     "custom_profile",
                                     "hash"])

# def is_similar(content1, content2, threshold=95):
#     """Compare deux contenus textuels et retourne True s'ils sont similaires à plus de 'threshold%'."""
#     if pd.isna(content1) or pd.isna(content2):
#         return False
#     similarity = fuzz.ratio(content1, content2)
#     return similarity >= threshold

def merge_dataframes(progress_dict, stored_df, new_df, use_llm, llm_config, language_filter):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""

    # Load client LLM
    client = None
    if use_llm:
        if llm_config["provider"] == "ChatGPT":
            client = OpenAI(api_key=llm_config.get("gpt_api_key"))
        elif llm_config["provider"] == "Mistral":
            client = Mistral(api_key=llm_config.get("mistral_api_key"))
        elif llm_config["provider"] == "Local":
            client = None

    if stored_df.empty:
        if use_llm:
            tqdm.pandas()
            new_df = new_df.progress_apply(lambda row: add_LLM_comment(client, llm_config, row), axis=1)
        return new_df

    # Filtrer les nouvelles lignes qui n'existent pas déjà dans stored_df
    new_rows = []
    # Conversion en set avant la boucle : le test `in` sur un set est O(1)
    # contre O(n) sur un tableau numpy — évite une déduplication en O(n²).
    stored_hashes = set(stored_df['hash'].values)
    stored_links = set(stored_df['link'].values)
    # for _, new_row in tqdm(new_df.iterrows(), total=len(new_df), desc="Traitement des offres récupérées"):
    for _, new_row in new_df.iterrows():
        if new_row['hash'] not in stored_hashes:
            if new_row['link'] not in stored_links:
                if all(language_filter.values()) or is_language_allowed(language_filter, new_row['content']):
        # if not stored_df['link'].str.contains(new_row['link'], na=False).any():
            # Vérifier si le contenu est trop similaire à un contenu existant
            # if not any(is_similar(new_row['content'], existing_content) for existing_content in stored_df['content']):
                    new_rows.append(new_row)

    for i, new_row in tqdm(enumerate(new_rows), total=len(new_rows), desc="Traitement des offres récupérées"):
        if use_llm:
            new_rows[i] = add_LLM_comment(client, llm_config, new_row)
            # Pause proactive pour rester sous le seuil de rate limit du provider LLM.
            # Le décorateur @backoff gère les 429 reçus, mais cette pause réduit
            # la probabilité d'en recevoir un en premier lieu (~2 req/s max).
            time.sleep(0.5)
        progress_dict["Traitement des nouvelles offres (LLM)"] = (i + 1, len(new_rows))

    if new_rows:
        new_data = pd.DataFrame(new_rows)
        return pd.concat([stored_df, new_data], ignore_index=True)
    else:
        return stored_df

def save_data(df):
    if not os.path.exists("data"):
        os.makedirs("data")
    df.to_csv("data/job.csv", index=False, sep=";", encoding="utf-8")


def update_store_data(progress_dict):
    # Load env variable
    # load_dotenv()
    try:
        config_file = "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        active_platforms = [Platform[key].value for key, active in config["launch_scrap"].items() if active]

        new_df = get_all_job(progress_dict, active_platforms, config["use_multithreading"])

        # Si tous les scrapers ont échoué, on ne touche pas au CSV existant :
        # écraser data/job.csv avec un DataFrame sans colonnes casserait app.py
        # (qui s'attend à trouver les colonnes date, title, etc.).
        if new_df.empty:
            print("Aucune offre collectée (tous les scrapers ont échoué), sauvegarde annulée.")
            return True

        store_df = get_store_data()
        # .get() avec valeur par défaut : rétrocompatibilité avec les anciens
        # config.json qui ne contiennent pas encore la clé "language_filter".
        merged_df = merge_dataframes(progress_dict, store_df, new_df, config["use_llm"], config["llm"], config.get("language_filter", {"fr": True, "en": True, "autre": True}))
        save_data(merged_df)

        return True
    except Exception as e:
        print(e)
        return False


if __name__ == "__main__":
    progress_dict = {
        "WelcomeToTheJungle": (0, 1),
        "Linkedin": (0, 1),
        "Apec": (0, 1),
        "ServicePublic": (0, 1),
        "HelloWork": (0, 1),
        "FranceTravail": (0, 1),
        "Traitement des nouvelles offres (LLM)": (0, 1)
    }
    update_store_data(progress_dict)







