import pandas as pd
import os
import json
import time
from datetime import datetime
import asyncio
import shutil
from openai import OpenAI
from mistralai.client import Mistral
from tqdm import tqdm
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraping.FranceTravail import FranceTravail
from scraping.HelloWork import HelloWork
from scraping.WelcomeToTheJungle import WelcomeToTheJungle
from scraping.Apec import Apec
from scraping.Linkedin import Linkedin
from scraping.ServicePublic import ServicePublic
from scraping.utils import add_LLM_comment, is_language_allowed, add_LLM_comment_and_track_progress
from JobColumns import JobColumns

CONFIG_FILE = "config.json"
DATA_FILE = "data/job.csv"

DEFAULT_CONFIG = {
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
    "keyword_mode": {
        "wttj": "one_by_one",
        "apec": "or",
        "linkedin": "or",
        "sp": "one_by_one",
        "hw": "one_by_one",
        "ft": "one_by_one"
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


def _backfill_defaults(config, defaults):
    """Ajoute récursivement les clés manquantes d'un config.json existant (ex: keyword_mode
    absent d'un fichier sauvegardé avant l'ajout de cette fonctionnalité), sans écraser les
    valeurs déjà présentes."""
    for key, default_value in defaults.items():
        if key not in config:
            config[key] = default_value
        elif isinstance(default_value, dict) and isinstance(config[key], dict):
            _backfill_defaults(config[key], default_value)
    return config

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        return _backfill_defaults(config, DEFAULT_CONFIG)
    else:
        return _backfill_defaults({}, DEFAULT_CONFIG)

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
    return pd.DataFrame(columns=[JobColumns.TITLE, JobColumns.CONTENT, JobColumns.COMPANY, JobColumns.LINK,
        JobColumns.PLATFORM, JobColumns.DATE, JobColumns.IS_READ, JobColumns.IS_APPLY,
        JobColumns.IS_REFUSED, JobColumns.IS_GOOD_OFFER, JobColumns.COMMENT,
        JobColumns.SCORE, JobColumns.CUSTOM_PROFILE, JobColumns.DAYS_DIFF])


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

    results = []
    if is_multiproc:
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
        for cls in all_platforms:
            try:
                results.append(run_source(cls))
            except Exception as e:
                progress_dict[cls.__name__] = (1, 1)
                print(f"Erreur lors du scraping de {cls.__name__}: {e}")

    # Guard : si tous les scrapers ont échoué, pd.concat([]) lèverait une ValueError.
    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


async def _indexed_task(coro, i, fallback_row):
    """Wrapper retournant (i, result) — capture exceptions pour garantir la progression."""
    try:
        result = await coro
    except Exception as e:
        print(f"[LLM ERROR] Tâche {i} échouée : {type(e).__name__}: {e}")
        result = fallback_row
    return i, result

def apply_pre_filter(row, pre_filter_config):
    """Applique le pré-filtre regex sur title + content. Retourne True si l'offre passe, False sinon."""
    if not pre_filter_config.get("enabled", False):
        return True  # Pre-filtre désactivé

    text = (row.get("title", "") + " " + row.get("content", "")).lower()

    # Vérifier la blacklist (si un mot y est, rejeter)
    blacklist = pre_filter_config.get("blacklist", [])
    for word in blacklist:
        if word.lower() in text:
            return False

    # Vérifier la whitelist (si activée, au moins un mot doit être présent)
    whitelist = pre_filter_config.get("whitelist", [])
    if whitelist and len(whitelist) > 0:
        return any(word.lower() in text for word in whitelist)

    return True  # Passe le filtre

async def merge_dataframes(progress_dict, stored_df, new_df, use_llm, llm_config, language_filter, pre_filter_config=None):
    """Ajoute les nouvelles entrées du new_df à stored_df en vérifiant l'unicité sur 'link' et la similarité sur 'content'."""
    # Initialiser pré_filter_config par défaut
    if pre_filter_config is None:
        pre_filter_config = {"enabled": False}

    # Load client LLM
    client = None
    if use_llm:
        if llm_config["provider"] == "ChatGPT":
            gpt_api_key = os.getenv("GPT_API_KEY") or llm_config.get("gpt_api_key")
            client = OpenAI(api_key=gpt_api_key)
        elif llm_config["provider"] == "Mistral":
            mistral_api_key = os.getenv("MISTRAL_API_KEY") or llm_config.get("mistral_api_key")
            client = Mistral(api_key=mistral_api_key)
        elif llm_config["provider"] == "Local":
            client = None

    if stored_df.empty:
       # Apply pre-filter row by row (same logic as non-empty case)
        filtered_rows = []
        for _, row in new_df.iterrows():
            if apply_pre_filter(row, pre_filter_config):
                filtered_rows.append(row)
        new_df = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame()
        if use_llm:
            total = len(new_df)
            progress_dict["Traitement des nouvelles offres (LLM)"] = (0, total if total > 0 else 1)

            updated_rows = []

            if llm_config["provider"] == "Mistral":
                # Pour Mistral: utiliser asyncio.wait(FIRST_COMPLETED) pour progres monotone et exception handling explicite
                orig_rows = list(new_df.iterrows())
                tasks = [
                    asyncio.create_task(_indexed_task(add_LLM_comment(client, llm_config, row), i, row))
                    for i, (_, row) in enumerate(orig_rows)
                ]
                updated_rows = [None] * total
                pending = set(tasks)
                completion_count = 0
                while pending:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        orig_i, result = task.result()  # pas d'exception : _indexed_task les capture
                        updated_rows[orig_i] = result
                        completion_count += 1
                        progress_dict["Traitement des nouvelles offres (LLM)"] = (
                            completion_count, total if total > 0 else 1
                        )
            else:
                for i, (_, row) in enumerate(tqdm(new_df.iterrows(), total=total, desc="Traitement des offres récupérées")):
                    result = await add_LLM_comment_and_track_progress(client, llm_config, row, i, total, progress_dict)
                    updated_rows.append(result)
            new_df = pd.DataFrame(updated_rows)
            progress_dict["Traitement des nouvelles offres (LLM)"] = (max(total, 1), max(total, 1))
        return new_df

    stored_hashes = set(stored_df['hash'].dropna().values)
    stored_links = set(stored_df['link'].dropna().values)

    # Filtrage initial des nouvelles offres uniques
    new_rows = []
    for _, new_row in new_df.iterrows():
        if new_row['hash'] not in stored_hashes and new_row['link'] not in stored_links:
            if all(language_filter.values()) or is_language_allowed(language_filter, str(new_row['content'])):
                new_rows.append(new_row)

    total_new = len(new_rows)

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

    total_filtered = len(filtered_rows)
    if total_filtered == 0:
        print("Aucune nouvelle offre à traiter par le LLM (toutes filtrées ou déjà existantes).")
    progress_dict["Traitement des nouvelles offres (LLM)"] = (0, total_filtered if total_filtered > 0 else 1)
    for i, new_row in tqdm(enumerate(filtered_rows), total=total_filtered, desc="Traitement des offres récupérées"):
        # Appeler LLM seulement si score n'a pas déjà été assigné (pré-filtre)
        if use_llm and new_row.get("comment") != "Filtré (pré-filtre)":
            filtered_rows[i] = await add_LLM_comment_and_track_progress(client, llm_config, new_row, i, total_filtered, progress_dict)
        else:
            # Guarantee progress dictionary is still updated when LLM is skipped
            progress_dict["Traitement des nouvelles offres (LLM)"] = (i + 1, total_filtered if total_filtered > 0 else 1)

    progress_dict["Traitement des nouvelles offres (LLM)"] = (max(total_filtered, 1), max(total_filtered, 1))

    if filtered_rows:
        new_data = pd.DataFrame(filtered_rows)
        return pd.concat([stored_df, new_data], ignore_index=True)
    else:
        return stored_df

def save_data(df):
    os.makedirs("data", exist_ok=True)
    df.to_csv(DATA_FILE, index=False, sep=";", encoding="utf-8")


async def update_store_data(progress_dict):
    try:
        config = load_config()
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
        merged_df = await merge_dataframes(
            progress_dict, store_df, new_df,
            config["use_llm"],
            config["llm"],
            config.get("language_filter", {"fr": True, "en": True, "autre": True}),
            config.get("pre_filter", {"enabled": False})
        )
        save_data(merged_df)

        return True
    except Exception as e:
        print(f"Erreur critique dans update_store_data: {e}")
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
    asyncio.run(update_store_data(progress_dict))







