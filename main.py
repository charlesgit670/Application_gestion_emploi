import pandas as pd
import os
import multiprocessing
from rapidfuzz import fuzz

from scraping.WelcomeToTheJungle import WelcomeToTheJungle
from scraping.Apec import Apec
from scraping.utils import measure_time

@measure_time
def get_all_job():
    with multiprocessing.Pool(processes=2) as pool:
        results = pool.map(get_jobs_from_source, [Apec, WelcomeToTheJungle])

    df = pd.concat(results)
    return df


def get_jobs_from_source(source_class):
    source = source_class()
    return source.getJob()


def get_store_data():
    file_path = "data/job.csv"

    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep=";")
    else:
        return pd.DataFrame(columns=["title", "content", "company", "link", "is_read", "is_apply", "is_refused"])

def is_similar(content1, content2, threshold=95):
    """Compare deux contenus textuels et retourne True s'ils sont similaires à plus de 'threshold%'."""
    if pd.isna(content1) or pd.isna(content2):
        return False
    similarity = fuzz.ratio(content1, content2)
    return similarity >= threshold

def merge_dataframes(stored_df, new_df):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""

    if stored_df.empty:
        return new_df

    # Filtrer les nouvelles lignes qui n'existent pas déjà dans stored_df
    new_rows = []

    for _, new_row in new_df.iterrows():
        if not stored_df['link'].str.contains(new_row['link'], na=False).any():
            # Vérifier si le contenu est trop similaire à un contenu existant
            if not any(
                    is_similar(new_row['content'], existing_content) for existing_content in stored_df['content']):
                new_rows.append(new_row)

    if new_rows:
        new_data = pd.DataFrame(new_rows)
        return pd.concat([stored_df, new_data], ignore_index=True)
    else:
        return stored_df


def update_store_data():
    new_df = get_all_job()
    store_df = get_store_data()
    merged_df = merge_dataframes(store_df, new_df)
    merged_df.to_csv("data/job.csv", index=False, sep=";")




if __name__ == "__main__":
    # Met à jour les données à partir du scraping des différents site d'offre
    update_store_data()








