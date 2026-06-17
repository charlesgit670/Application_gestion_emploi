import pandas as pd
import os
import json
import time
from datetime import datetime
import shutil
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

CONFIG_FILE = "config.json"
DATA_FILE = "data/job.csv"


class Platform(Enum):
    wttj = WelcomeToTheJungle
    apec = Apec
    linkedin = Linkedin
    sp = ServicePublic
    hw = HelloWork
    ft = FranceTravail


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "keywords": [],
            "url": {
                "wttj": "",
                "apec": "",
                "linkedin": "",
                "sp": ""
            },
            "launch_scrap": {
                "wttj": False,
                "apec": False,
                "linkedin": False,
                "sp": False,
                "hw": False,
                "ft": False
            },
            "filter_day_scrap": 7,
            "language_filter": {
                "fr": True,
                "en":  False,
                "autre": False
            },
            "use_multithreading": False,
            "use_llm": False,
            "llm": {
                "provider": "Local",
                "gpt_api_key": "",
                "mistral_api_key": "",
                "generate_score": False,
                "prompt_score": "",
                "generate_custom_profile": False,
                "prompt_custom_profile": "",
                "cv": ""
            }
        }


def get_store_data():
    backup_dir = "data/backup/"
    if os.path.exists(DATA_FILE):
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(backup_dir, f"job_backup_{timestamp}.csv")
        try:
            shutil.copy(DATA_FILE, backup_file)
            return pd.read_csv(DATA_FILE, sep=";", encoding="utf-8")
        except Exception:
            pass
    return pd.DataFrame(columns=["title", "content", "company", "link", "date", "is_read",
                                 "is_apply", "is_refused", "is_good_offer", "comment",
                                 "score", "custom_profile", "hash"])


def get_all_job(progress_dict, all_platforms, is_multiproc):
    def run_source(source_class):
        name = source_class.__name__
        platform = source_class()

        def update_callback(current, total):
            progress_dict[name] = (current, total)

        return platform.getJob(update_callback=update_callback)

    results = []
    if is_multiproc:
        with ThreadPoolExecutor(max_workers=len(all_platforms)) as executor:
            futures = {executor.submit(run_source, cls): cls for cls in all_platforms}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"Erreur lors du scraping de {futures[future].__name__}: {e}")
    else:
        for cls in all_platforms:
            try:
                results.append(run_source(cls))
            except Exception as e:
                print(f"Erreur lors du scraping de {cls.__name__}: {e}")

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


def merge_dataframes(progress_dict, stored_df, new_df, use_llm, llm_config, language_filter):
    """Fusionne et traite de manière robuste les lignes par le LLM sans altérer les structures."""
    if new_df.empty:
        return stored_df

    # Initialisation du client LLM
    client = None
    if use_llm:
        if llm_config.get("provider") == "ChatGPT":
            client = OpenAI(api_key=llm_config.get("gpt_api_key"))
        elif llm_config.get("provider") == "Mistral":
            client = Mistral(api_key=llm_config.get("mistral_api_key"))

    if stored_df.empty:
        stored_df = pd.DataFrame(columns=["title", "content", "company", "link", "date", "is_read",
                                          "is_apply", "is_refused", "is_good_offer", "comment",
                                          "score", "custom_profile", "hash"])

    stored_hashes = set(stored_df['hash'].dropna().values)
    stored_links = set(stored_df['link'].dropna().values)

    # Filtrage initial des nouvelles offres uniques
    valid_rows = []
    for _, new_row in new_df.iterrows():
        if new_row['hash'] not in stored_hashes and new_row['link'] not in stored_links:
            if all(language_filter.values()) or is_language_allowed(language_filter, str(new_row['content'])):
                valid_rows.append(new_row)

    if not valid_rows:
        print("Aucune nouvelle offre unique à traiter.")
        return stored_df

    # Création d'un DataFrame temporaire propre pour le traitement
    new_df_filtered = pd.DataFrame(valid_rows).reset_index(drop=True)
    total_to_process = len(new_df_filtered)

    # Traitement itératif sécurisé
    for i in tqdm(range(total_to_process), desc="Traitement des offres par le LLM"):
        row = new_df_filtered.iloc[i].copy()
        if use_llm:
            try:
                processed_row = add_LLM_comment(client, llm_config, row)
                # Ré-injection sélective dans le DataFrame filtré
                new_df_filtered.iloc[i] = processed_row
                time.sleep(0.5)  # Respect du rate limit
            except Exception as e:
                print(f"Erreur lors du traitement LLM sur la ligne {i}: {e}")

        progress_dict["Traitement des nouvelles offres (LLM)"] = (i + 1, total_to_process)

    return pd.concat([stored_df, new_df_filtered], ignore_index=True)


def save_data(df):
    os.makedirs("data", exist_ok=True)
    df.to_csv(DATA_FILE, index=False, sep=";", encoding="utf-8")


def update_store_data(progress_dict):
    try:
        config = load_config()
        active_platforms = [Platform[key].value for key, active in config["launch_scrap"].items() if active]
        new_df = get_all_job(progress_dict, active_platforms, config["use_multithreading"])

        if new_df.empty:
            print("Aucune offre collectée, sauvegarde annulée.")
            return True

        store_df = get_store_data()
        merged_df = merge_dataframes(
            progress_dict, store_df, new_df,
            config["use_llm"], config["llm"],
            config.get("language_filter", {"fr": True, "en": True, "autre": True})
        )
        save_data(merged_df)
        return True
    except Exception as e:
        print(f"Erreur critique dans update_store_data: {e}")
        return False


if __name__ == "__main__":
    init_progress = {
        "WelcomeToTheJungle": (0, 1), "Linkedin": (0, 1), "Apec": (0, 1),
        "ServicePublic": (0, 1), "HelloWork": (0, 1), "FranceTravail": (0, 1),
        "Traitement des nouvelles offres (LLM)": (0, 1)
    }
    update_store_data(init_progress)