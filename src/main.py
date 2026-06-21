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
from scraping.utils import measure_time, add_LLM_comment, is_language_allowed, add_LLM_comment_and_track_progress
from concurrent.futures import ThreadPoolExecutor, as_completed


class Platform(Enum):
    wttj = WelcomeToTheJungle
    apec = Apec
    linkedin = Linkedin
    sp = ServicePublic
    hw = HelloWork
    ft = FranceTravail


def validate_scraping_config(config):
    errors = []
    allowed_modes = {"one_by_one", "or", "all"}

    keywords = config.get("keywords", [])
    if not isinstance(keywords, list) or not any(str(k).strip() for k in keywords):
        errors.append("keywords doit être une liste non vide")

    launch_scrap = config.get("launch_scrap", {})
    if not isinstance(launch_scrap, dict):
        errors.append("launch_scrap doit être un objet")
        launch_scrap = {}

    urls = config.get("url", {})
    keyword_modes = config.get("keyword_mode", {})
    active_keys = [key for key, active in launch_scrap.items() if active]

    for key in active_keys:
        if key not in Platform.__members__:
            errors.append(f"plateforme inconnue dans launch_scrap: {key}")
            continue
        if not urls.get(key):
            errors.append(f"url.{key} manquant")
        mode = keyword_modes.get(key)
        if not mode:
            errors.append(f"keyword_mode.{key} manquant")
        elif mode not in allowed_modes:
            errors.append(f"keyword_mode.{key} invalide: {mode}")

    if errors:
        print("Configuration invalide:")
        for err in errors:
            print(f" - {err}")
        return False
    return True

def get_all_job(progress_dict, all_platforms, is_multiproc):

    def run_source(source_class):
        name = source_class.__name__
        platform = source_class()
        callback_state = {"updated": False}

        def update_callback(current, total):
            safe_total = total if total and total > 0 else 1
            safe_current = max(0, min(current, safe_total))
            progress_dict[name] = (safe_current, safe_total)
            callback_state["updated"] = True

        df = platform.getJob(update_callback=update_callback)

        # Garantit un état terminal pour la barre même si le scraper n'émet
        # aucune progression (ex: zéro résultat très tôt).
        if not callback_state["updated"]:
            progress_dict[name] = (1, 1)
        else:
            current, total = progress_dict.get(name, (0, 1))
            if current < total:
                progress_dict[name] = (total, total)

        return df

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
                    progress_dict[futures[future].__name__] = (1, 1)
                    print(f"Erreur lors du scraping de {futures[future].__name__}: {e}")
    else:
        results = []
        for cls in all_platforms:
            try:
                results.append(run_source(cls))
            except Exception as e:
                progress_dict[cls.__name__] = (1, 1)
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

def apply_pre_filter(row, pre_filter_config):
    """Applique le pré-filtre regex sur title + content. Retourne True si l'offre passe, False sinon."""
    if not pre_filter_config.get("enabled", False):
        return True

    text = (row.get("title", "") + " " + row.get("content", "")).lower()

    blacklist = pre_filter_config.get("blacklist", [])
    for word in blacklist:
        if word.lower() in text:
            return False

    whitelist = pre_filter_config.get("whitelist", [])
    if whitelist and len(whitelist) > 0:
        return any(word.lower() in text for word in whitelist)

    return True

def merge_dataframes(progress_dict, stored_df, new_df, use_llm, llm_config, language_filter, pre_filter_config=None):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""
    if pre_filter_config is None:
        pre_filter_config = {"enabled": False}

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
        filtered_rows = []
        for _, row in new_df.iterrows():
            if apply_pre_filter(row, pre_filter_config):
                filtered_rows.append(row)
        new_df = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame()
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

    # Étape 1 : Pré-filtrage par regex avant LLM (impact fort)
    filtered_rows = []
    for row in new_rows:
        if apply_pre_filter(row, pre_filter_config):
            filtered_rows.append(row)
        else:
            # Offre rejetée par pré-filtre : marquer score=0 sans appel LLM
            row["score"] = 0
            row["is_good_offer"] = 0
            row["comment"] = "Filtré (pré-filtre)"
            row["custom_profile"] = ""
            filtered_rows.append(row)

    for i, new_row in tqdm(enumerate(filtered_rows), total=len(filtered_rows), desc="Traitement des offres récupérées"):
        if use_llm and new_row.get("comment") != "Filtré (pré-filtre)":
            filtered_rows[i] = add_LLM_comment_and_track_progress(client, llm_config, new_row, i, len(filtered_rows), progress_dict)
            time.sleep(0.5)
        else:
            safe_total = len(filtered_rows) if len(filtered_rows) > 0 else 1
            progress_dict["Traitement des nouvelles offres (LLM)"] = (i + 1, safe_total)

    progress_dict["Traitement des nouvelles offres (LLM)"] = (max(len(filtered_rows), 1), max(len(filtered_rows), 1))

    if filtered_rows:
        new_data = pd.DataFrame(filtered_rows)
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

        if not validate_scraping_config(config):
            return False

        active_platforms = [Platform[key].value for key, active in config["launch_scrap"].items() if active]
        if not active_platforms:
            print("Aucune plateforme active dans launch_scrap, scraping annulé.")
            return True

        new_df = get_all_job(progress_dict, active_platforms, config["use_multithreading"])

        # Si aucun scraper n'a renvoyé d'offre valide, on ne touche pas au CSV
        # existant pour éviter d'écraser des colonnes attendues par l'app.
        if new_df.empty:
            print("Aucune offre valide collectée, sauvegarde annulée.")
            return True

        store_df = get_store_data()
        # .get() avec valeur par défaut : rétrocompatibilité avec les anciens
        # config.json qui ne contiennent pas encore la clé "language_filter".
        merged_df = merge_dataframes(
            progress_dict, store_df, new_df,
            config["use_llm"],
            config["llm"],
            config.get("language_filter", {"fr": True, "en": True, "autre": True}),
            config.get("pre_filter", {"enabled": False})
        )
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







