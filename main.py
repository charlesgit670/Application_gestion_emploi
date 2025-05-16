import pandas as pd
import os
import multiprocessing
from rapidfuzz import fuzz
from datetime import datetime
import shutil
from dotenv import load_dotenv
from openai import OpenAI
# from mistralai import Mistral
from tqdm import tqdm

from scraping.WelcomeToTheJungle import WelcomeToTheJungle
from scraping.Apec import Apec
from scraping.Linkedin import Linkedin
from scraping.utils import measure_time, add_LLM_comment

@measure_time
def get_all_job(is_multiproc=True):
    all_platform = [Linkedin, WelcomeToTheJungle, Apec]
    # all_platform = [Apec]
    if is_multiproc:
        nbr_proc = len(all_platform)
        with multiprocessing.Pool(processes=nbr_proc) as pool:
            results = pool.map(get_jobs_from_source, all_platform)
    else:
        results = []
        for p in all_platform:
            results.append(p().getJob())

    df = pd.concat(results)
    return df


def get_jobs_from_source(source_class):
    source = source_class()
    return source.getJob()


def get_store_data():
    file_path = "data/backup/job.csv"
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
                                     "is_read",
                                     "is_apply",
                                     "is_refused",
                                     "is_good_offer",
                                     "comment",
                                     "score",
                                     "custom_profile"])

def is_similar(content1, content2, threshold=95):
    """Compare deux contenus textuels et retourne True s'ils sont similaires à plus de 'threshold%'."""
    if pd.isna(content1) or pd.isna(content2):
        return False
    similarity = fuzz.ratio(content1, content2)
    return similarity >= threshold

def merge_dataframes(stored_df, new_df, local_LLM):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""
    if stored_df.empty:
        return new_df

    # Filtrer les nouvelles lignes qui n'existent pas déjà dans stored_df
    new_rows = []

    # Load client LLM
    client = None
    if not local_LLM:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    for _, new_row in tqdm(new_df.iterrows(), total=len(new_df), desc="Traitement des offres récupérées"):
        if not stored_df['link'].str.contains(new_row['link'], na=False).any():
            # Vérifier si le contenu est trop similaire à un contenu existant
            if not any(is_similar(new_row['content'], existing_content) for existing_content in stored_df['content']):
                new_row = add_LLM_comment(client, new_row)
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


def update_store_data(is_multiproc=True, local_LLM=False):
    new_df = get_all_job(is_multiproc)
    store_df = get_store_data()
    merged_df = merge_dataframes(store_df, new_df, local_LLM)
    save_data(merged_df)




if __name__ == "__main__":
    # Load env variable
    load_dotenv()
    # Met à jour les données à partir du scraping des différents site d'offre
    update_store_data(is_multiproc=True, local_LLM=True)








