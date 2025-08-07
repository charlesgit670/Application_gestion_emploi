import pandas as pd
import os
import json
from rapidfuzz import fuzz
from datetime import datetime
import shutil
from dotenv import load_dotenv
from openai import OpenAI
# from mistralai import Mistral
from tqdm import tqdm
from enum import Enum

from scraping.WelcomeToTheJungle import WelcomeToTheJungle
from scraping.Apec import Apec
from scraping.Linkedin import Linkedin
from scraping.utils import measure_time, add_LLM_comment
from concurrent.futures import ThreadPoolExecutor


class Platform(Enum):
    wttj = WelcomeToTheJungle
    apec = Apec
    linkedin = Linkedin

def get_all_job(progress_dict, all_platforms, is_multiproc=True):

    def run_source(source_class):
        name = source_class.__name__
        platform = source_class()

        def update_callback(current, total):
            progress_dict[name] = (current, total)

        return platform.getJob(update_callback=update_callback)

    if is_multiproc:
        with ThreadPoolExecutor(max_workers=len(all_platforms)) as executor:
            results = list(executor.map(run_source, all_platforms))
    else:
        results = []
        for cls in all_platforms:
            results.append(cls.getJob())

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
        return pd.read_csv(file_path, sep=";")
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

def is_similar(content1, content2, threshold=95):
    """Compare deux contenus textuels et retourne True s'ils sont similaires à plus de 'threshold%'."""
    if pd.isna(content1) or pd.isna(content2):
        return False
    similarity = fuzz.ratio(content1, content2)
    return similarity >= threshold

def merge_dataframes(stored_df, new_df, use_llm, llm_config):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""

    # Load client LLM
    client = None
    if use_llm and not llm_config["local"]:
        client = OpenAI(api_key=llm_config["gpt_api_key"])


    if stored_df.empty:
        if use_llm:
            new_df = new_df.apply(lambda row: add_LLM_comment(client, llm_config, row), axis=1)
        return new_df

    # Filtrer les nouvelles lignes qui n'existent pas déjà dans stored_df
    new_rows = []
    for _, new_row in tqdm(new_df.iterrows(), total=len(new_df), desc="Traitement des offres récupérées"):
        if not new_row['hash'] in stored_df['hash'].values:
            if not new_row['link'] in stored_df['link'].values:
        # if not stored_df['link'].str.contains(new_row['link'], na=False).any():
            # Vérifier si le contenu est trop similaire à un contenu existant
            # if not any(is_similar(new_row['content'], existing_content) for existing_content in stored_df['content']):
                if use_llm:
                    new_row = add_LLM_comment(client, llm_config, new_row)
                new_rows.append(new_row)

    if new_rows:
        new_data = pd.DataFrame(new_rows)
        return pd.concat([stored_df, new_data], ignore_index=True)
    else:
        return stored_df

def save_data(df):
    if not os.path.exists("data"):
        os.makedirs("data")
    df.to_csv("data/job.csv", index=False, sep=";")


def update_store_data(progress_dict):
    # Load env variable
    # load_dotenv()
    try:
        config_file = "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        active_platforms = [Platform[key].value for key, active in config["launch_scrap"].items() if active]

        new_df = get_all_job(progress_dict, active_platforms, config["use_multithreading"])
        store_df = get_store_data()
        merged_df = merge_dataframes(store_df, new_df, config["use_llm"], config["llm"])
        save_data(merged_df)

        return True
    except Exception as e:
        print(e)
        return False


if __name__ == "__main__":
    progress_dict = {
        "WelcomeToTheJungle": (0, 0),
        "Linkedin": (0, 0),
        "Apec": (0, 0),
    }
    update_store_data(progress_dict)







