import streamlit as st
import threading
import time
import json
import os
import asyncio
from main import update_store_data, load_config

from app_utils import ensure_data_loaded

CONFIG_FILE = "config.json"
DEFAULT_CONFIG_FILE = "config_default.json"

st.title("🔍 Configuration & Lancement du Scraping")


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


config = load_config()
ensure_data_loaded()

# --- BLOC PANNEAU DE CONFIGURATION ---
with st.expander("⚙️ Paramètres des Scrapers et Filtres", expanded=True):
    st.header("🔑 Mots-clés")
    keywords = st.text_area("Entrez les mots-clés (un par ligne)", "\n".join(config.get("keywords", [])))
    config["keywords"] = [k.strip() for k in keywords.splitlines() if k.strip()]

    st.header("🔗 Configuration des Plateformes")
    platforms = [
        ("wttj", "Welcome To The Jungle"), ("apec", "APEC"), ("linkedin", "LinkedIn"),
        ("sp", "Service Public"), ("hw", "HelloWork"), ("ft", "France Travail")
    ]

    for key, label in platforms:
        col_url, col_active = st.columns([4, 1])
        with col_url:
            config["url"][key] = st.text_input(f"URL de recherche {label}", config["url"].get(key, ""))
        with col_active:
            st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            config["launch_scrap"][key] = st.checkbox("Activer", config["launch_scrap"].get(key, False),
                                                      key=f"check_{key}")

    st.header("⚙️ Options générales")
    config["filter_day_scrap"] = st.number_input("Indiquer en jours l'ancienneté maximale des offres scrapées",
                                                 value=config.get("filter_day_scrap", 7), min_value=1)

    lang_dict = config.get("language_filter", {"fr": True, "en": False, "autre": False})
    default_selected = [k for k, v in lang_dict.items() if v]
    selected_langs = st.multiselect("Langues autorisées", list(lang_dict.keys()), default=default_selected)
    config["language_filter"] = {k: (k in selected_langs) for k in lang_dict.keys()}

    config["use_multithreading"] = st.checkbox(
        "Utiliser le multithreading (permet de scraper plusieurs sites en même temps)",
        config.get("use_multithreading", True))

    st.header("🧠 Paramètres d'Analyse (LLM)")
    config["use_llm"] = st.checkbox("Activer l'évaluation par LLM", config.get("use_llm", False))

    if config["use_llm"]:
        provider_options = ["Local", "ChatGPT", "Mistral"]
        current_provider = config["llm"].get("provider", "Local")
        if current_provider not in provider_options: current_provider = "Local"

        config["llm"]["provider"] = st.radio("Choisissez le fournisseur LLM :", provider_options,
                                             index=provider_options.index(current_provider))

        if config["llm"]["provider"] == "ChatGPT":
            config["llm"]["gpt_api_key"] = st.text_input("Clé API GPT", config["llm"].get("gpt_api_key", ""),
                                                         type="password")
        elif config["llm"]["provider"] == "Mistral":
            config["llm"]["mistral_api_key"] = st.text_input("Clé API Mistral",
                                                             config["llm"].get("mistral_api_key", ""), type="password")

        config["llm"]["generate_score"] = st.checkbox(
            "Générer un score pour les offres et un commentaire (Filtre automatique)",
            config["llm"].get("generate_score", True))
        if config["llm"]["generate_score"]:
            config["llm"]["prompt_score"] = st.text_area("Prompt d'évaluation (Score & Justification)",
                                                         config["llm"].get("prompt_score", ""), height=250)

        config["llm"]["generate_custom_profile"] = st.checkbox(
            "Générer une proposition d'adaptation de profil en fonction de l'offre",
            config["llm"].get("generate_custom_profile", False))
        if config["llm"]["generate_custom_profile"]:
            config["llm"]["prompt_custom_profile"] = st.text_area("Prompt d'adaptation de l'Objectif professionnel",
                                                                  config["llm"].get("prompt_custom_profile", ""))
            config["llm"]["cv"] = st.text_area("Texte brut de votre CV (Sert de base d'analyse pour le prompt)",
                                               config["llm"].get("cv", ""), height=200)

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("💾 Sauvegarder la configuration"):
            save_config(config)
            st.success("Configuration sauvegardée avec succès !")
    with col_reset:
        if st.button("♻️ Réinitialiser la configuration"):
            if os.path.exists(DEFAULT_CONFIG_FILE):
                with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
                    save_config(json.load(f))
                st.success("Configuration réinitialisée depuis config_default.json.")
                st.rerun()
            else:
                st.error("Fichier config_default.json introuvable.")

# --- BLOC INTERFACE DE SUIVI DU SCRAPING ---
st.write("---")
st.header("🚀 Lancement du Traitement")


# 1. Utilisation d'une fonction cachée pour créer un dictionnaire global
# qui NE PEUT PAS être supprimé par les reruns de Streamlit
@st.cache_resource
def get_global_progress():
    return {
        "WelcomeToTheJungle": [0, 1], "Linkedin": [0, 1], "Apec": [0, 1],
        "ServicePublic": [0, 1], "HelloWork": [0, 1], "FranceTravail": [0, 1],
        "Traitement des nouvelles offres (LLM)": [0, 1]
    }


@st.cache_resource
def get_thread_output():
    return {"status": "pending", "result": None}


# Récupération des pointeurs vers nos objets sécurisés
global_progress = get_global_progress()
thread_shared_output = get_thread_output()

# Initialisation des variables de contrôle basiques dans le session_state
if "scraping_running" not in st.session_state:
    st.session_state.scraping_running = False
if "success_scraping" not in st.session_state:
    st.session_state.success_scraping = None

# Bouton d'action principale
if st.button("▶️ Démarrer le Scraping", disabled=st.session_state.scraping_running):
    st.session_state.scraping_running = True
    st.session_state.success_scraping = None
    thread_shared_output["status"] = "running"
    thread_shared_output["result"] = None

    # Réinitialisation (utilisation de listes [0, 1] pour modification en place dans main.py)
    for k in global_progress:
        global_progress[k] = [0, 1]


    async def run_worker(prog_dict, output_holder):
        try:
            res = await update_store_data(prog_dict)
            output_holder["result"] = res
            output_holder["status"] = "finished"
        except Exception:
            output_holder["result"] = False
            output_holder["status"] = "failed"


    # On passe le dictionnaire global TRÈS éloigné de st.session_state au thread
    thread = threading.Thread(
        target=lambda: asyncio.run(run_worker(global_progress, thread_shared_output)),
    )
    thread.start()
    st.rerun()

# --- RENDER DE L'AVANCEMENT EN DIRECT ---
if st.session_state.scraping_running:
    status = thread_shared_output["status"]

    if status == "running":
        st.info("⏳ Scraping en cours... Vous pouvez changer de page, le traitement continue en arrière-plan.")

        # Affichage des barres en lisant le dictionnaire global sécurisé
        for platform, values in global_progress.items():
            current, total = values[0], values[1]
            percent = int((current / total) * 100) if total > 0 else 0
            percent = max(0, min(100, percent))
            st.progress(percent, text=f"**{platform}** : {current} / {total} traité(s) ({percent}%)")

        # Pause d'une seconde pour laisser l'interface respirer, puis rafraîchissement
        time.sleep(1)
        st.rerun()

    else:
        # Le thread a terminé son exécution (finished ou failed)
        st.session_state.success_scraping = thread_shared_output["result"]
        st.session_state.scraping_running = False
        st.cache_data.clear()  # Nettoyage du cache de données si nécessaire
        st.rerun()

# Affichage du résultat final persistant (uniquement visible sur cette page)
if st.session_state.success_scraping is not None:
    if st.session_state.success_scraping:
        st.success("🎉 Scraping et analyses terminés avec succès !")
    else:
        st.error("❌ Le processus s'est terminé mais une anomalie a été signalée ou le thread a planté.")