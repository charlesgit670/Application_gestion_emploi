import streamlit as st
import threading
import time
import asyncio
import pandas as pd
import json
import os

from main import update_store_data

# 🔄 Chemin du fichier de config
CONFIG_FILE = "config.json"
DEFAULT_CONFIG_FILE = "config_default.json"

def save_data(df, data_file="data/job.csv"):
    df.to_csv(data_file, sep=";", index=False, encoding="utf-8")

def get_color(score):
    r = int(255 - (score * 2.55))
    g = int(score * 2.55)
    return f"rgb({r},{g},0)"

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

def configuration_page():
    # 💾 Sauvegarder la configuration
    def save_config(config):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    # 🔁 Réinitialiser la configuration depuis config_default.json
    def reset_config():
        if os.path.exists(DEFAULT_CONFIG_FILE):
            with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
                default_config = json.load(f)
            save_config(default_config)
            return True
        else:
            return False

    # 🔧 Interface utilisateur Streamlit
    st.title("🔧 Configuration du Scraper")

    config = load_config()

    # 🎯 Section mots-clés
    st.header("🔑 Mots-clés")
    keywords = st.text_area("Entrez les mots-clés (un par ligne)", "\n".join(config["keywords"]))
    config["keywords"] = [k.strip() for k in keywords.splitlines() if k.strip()]

    # 🌐 Section URLs
    st.header("🔗 URLs des sites")
    config["url"]["wttj"] = st.text_input("WTTJ URL", config["url"]["wttj"])
    config["url"]["apec"] = st.text_input("APEC URL", config["url"]["apec"])
    config["url"]["linkedin"] = st.text_input("LinkedIn URL", config["url"]["linkedin"])
    config["url"]["sp"] = st.text_input("Service Public URL", config["url"]["sp"])
    config["url"]["hw"] = st.text_input("HelloWork URL", config["url"]["hw"])
    config["url"]["ft"] = st.text_input("France Travail URL", config["url"]["ft"])

    # 🚀 Sites à scraper
    st.header("📡 Lancer le scraping sur :")
    config["launch_scrap"]["wttj"] = st.checkbox("WTTJ", config["launch_scrap"]["wttj"])
    config["launch_scrap"]["apec"] = st.checkbox("APEC", config["launch_scrap"]["apec"])
    config["launch_scrap"]["linkedin"] = st.checkbox("LinkedIn", config["launch_scrap"]["linkedin"])
    config["launch_scrap"]["sp"] = st.checkbox("Service Public", config["launch_scrap"]["sp"])
    config["launch_scrap"]["hw"] = st.checkbox("HelloWork", config["launch_scrap"]["hw"])
    config["launch_scrap"]["ft"] = st.checkbox("France Travail", config["launch_scrap"]["ft"])

    # ⚙️ Options générales
    st.header("⚙️ Options générales")
    config["filter_day_scrap"] = st.number_input("Indiquer en jours l'ancienneté maximale des offres scrapées", value=config["filter_day_scrap"])

    default_selected = [k for k, v in config["language_filter"].items() if v]
    selected = st.multiselect(
        "Langues",
        config["language_filter"].keys(),
        default=default_selected
    )
    config["language_filter"] = {k: k in selected for k in config["language_filter"].keys()}

    config["use_multithreading"] = st.checkbox(
        "Utiliser le multithreading (permet de scrapper plusieurs sites en même temps mais demande plus de ressource)",
        config["use_multithreading"])
    config["use_llm"] = st.checkbox("Utiliser un LLM", config["use_llm"])

    # 🤖 Configuration LLM
    if config["use_llm"]:
        st.subheader("🧠 Paramètres du LLM")

        # config["llm"]["local"] = st.checkbox("LLM local", config["llm"]["local"])
        # if not config["llm"]["local"]:
        #     config["llm"]["gpt_api_key"] = st.text_input("Clé API GPT (laissez vide si non utilisée)",
        #                                                  config["llm"]["gpt_api_key"])

        # Choix du LLM : local, ChatGPT ou Mistral
        config["llm"]["provider"] = st.radio(
            "Choisissez le fournisseur LLM :",
            ["Local", "ChatGPT", "Mistral"],
            index=["Local", "ChatGPT", "Mistral"].index(config["llm"].get("provider", "Local"))
        )

        # Gestion des champs selon le choix
        if config["llm"]["provider"] == "ChatGPT":
            config["llm"]["gpt_api_key"] = st.text_input(
                "Clé API GPT",
                config["llm"].get("gpt_api_key", "")
            )

        elif config["llm"]["provider"] == "Mistral":
            config["llm"]["mistral_api_key"] = st.text_input(
                "Clé API Mistral",
                config["llm"].get("mistral_api_key", "")
            )

        config["llm"]["generate_score"] = st.checkbox(
            "Générer un score pour les offres et un commentaire (permet aussi de filtrer les offres 'score > 50')",
            config["llm"]["generate_score"])
        if config["llm"]["generate_score"]:
            config["llm"]["prompt_score"] = st.text_area("Adapter le prompt à vos besoin sans changer la struture",
                                                         config["llm"]["prompt_score"])
        config["llm"]["generate_custom_profile"] = st.checkbox("Générer un profile en fonction de l'offre",
                                                               config["llm"]["generate_custom_profile"])
        if config["llm"]["generate_custom_profile"]:
            config["llm"]["prompt_custom_profile"] = st.text_area("Entrez votre prompt pour générer votre profile",
                                                                  config["llm"]["prompt_custom_profile"])
            config["llm"]["cv"] = st.text_area("Le texte de votre CV afin de mieux adapter le résumé du profile",
                                               config["llm"]["cv"])

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Sauvegarder la configuration"):
            save_config(config)
            st.success("Configuration sauvegardée avec succès !")

    with col2:
        if st.button("♻️ Réinitialiser la configuration"):
            if reset_config():
                st.success("Configuration réinitialisée depuis config_default.json.")
                st.experimental_rerun()  # Recharge la page avec les nouvelles valeurs
            else:
                st.error("Fichier config_default.json introuvable.")

def scrapping_page():
    st.title("🔍 Scraping d'offres d’emploi")

    # Initialisation des états persistants
    if "scraping_running" not in st.session_state:
        st.session_state.scraping_running = False
    if "launch_clicked" not in st.session_state:
        st.session_state.launch_clicked = False
    if "scraping_started" not in st.session_state:
        st.session_state.scraping_started = False
    if "progress_dict" not in st.session_state:
        st.session_state.progress_dict = {
            "WelcomeToTheJungle": (0, 1),
            "Linkedin": (0, 1),
            "Apec": (0, 1),
            "ServicePublic": (0, 1),
            "HelloWork": (0, 1),
            "FranceTravail": (0, 1),
            "Traitement des nouvelles offres (LLM)": (0, 1),
        }
    if "progress_bars" not in st.session_state:
        st.session_state.progress_bars = {}

    # Conteneur principal pour garder l’ordre stable
    with st.container():
        # Bouton de lancement (avec protection double-clic)
        if st.button("🚀 Lancer le scraping", disabled=st.session_state.scraping_running):
            if not st.session_state.launch_clicked:
                st.session_state.launch_clicked = True
                st.session_state.scraping_running = True
                st.rerun()

        # Affichage (ou re-création) des barres de progression
        for platform, (current, total) in st.session_state.progress_dict.items():
            percent = int((current / total) * 100) if total > 0 else 0
            if platform not in st.session_state.progress_bars or st.session_state.progress_bars[platform] is None:
                st.session_state.progress_bars[platform] = st.progress(percent, text=f"{platform} : {current} offres ({percent}%)")
            else:
                st.session_state.progress_bars[platform].progress(
                    percent,
                    text=f"{platform} : {current} offres ({percent}%)"
                )

    # Démarrage réel du scraping
    if st.session_state.scraping_running and not st.session_state.scraping_started:
        st.session_state.scraping_started = True  # Évite plusieurs lancements

        # Réinitialise les barres et compteurs
        for k in st.session_state.progress_dict:
            st.session_state.progress_dict[k] = (0, 1)

        for k in st.session_state.progress_bars:
            st.session_state.progress_bars[k].progress(0, text=f"{k} (0 offres - 0%)")

        def run(progress_dict):
            success = asyncio.run(update_store_data(progress_dict))
            result_container["success"] = success

        progress_dict = st.session_state.progress_dict
        result_container = {}
        thread = threading.Thread(target=run, args=(progress_dict,))
        thread.start()

        # Boucle de suivi des barres
        while thread.is_alive():
            for platform in st.session_state.progress_dict:
                current, total = st.session_state.progress_dict[platform]
                percent = int((current / total) * 100) if total > 0 else 0

                # Recrée si besoin (protection post-navigation)
                if platform not in st.session_state.progress_bars or st.session_state.progress_bars[platform] is None:
                    st.session_state.progress_bars[platform] = st.progress(percent, text=f"{platform} : {current} offres ({percent}%)")
                else:
                    st.session_state.progress_bars[platform].progress(
                        percent,
                        text=f"{platform} : {current} offres ({percent}%)"
                    )
            time.sleep(0.2)

        # Affiche le message en fonction du résultat
        if result_container.get("success"):
            st.success("🎉 Scraping terminé avec succès !")
        else:
            st.error("❌ Une erreur est survenue pendant le scraping.")

        # Réinitialisation des états
        st.session_state.scraping_running = False
        st.session_state.launch_clicked = False
        st.session_state.scraping_started = False

    configuration_page()




def new_offer_page(df):
    # Filtrer les offres non lues
    unread_jobs = df[(df["is_read"] == 0) & (df["is_good_offer"] == 1)] \
        .sort_values(by=["days_diff", "score"], ascending=[True, False]) \
        .reset_index(drop=True)

    total_jobs = len(unread_jobs)

    if unread_jobs.empty:
        st.title(f"📌 Offres d'emploi")
        st.write("✅ Toutes les offres ont été lues !")
    else:
        st.title(f"📌 Offres d'emploi **{st.session_state.index + 1} / {total_jobs}**")
        current_index = st.session_state.index % total_jobs
        job = unread_jobs.iloc[current_index]

        st.subheader(job["title"])
        st.subheader(job["company"])
        st.markdown(f"[🔗 Lien vers l'offre]({job['link']})", unsafe_allow_html=True)
        st.write(
            f"Publié il y a **{int(job['days_diff'])}** jours"
            if pd.notna(job['days_diff'])
            else "Date de publication non renseignée"
        )
        score = int(job["score"])
        if score != -1:
            color = get_color(score)
            st.markdown(f"""
               <div style="margin: 20px 0; width: 60%; background-color: #eee; border-radius: 5px;">
                 <div style="width: {score}%; background-color: {color}; padding: 10px 0; border-radius: 5px; text-align: center; color: white; font-weight: bold;">
                   {score}%
                 </div>
               </div>
               """, unsafe_allow_html=True)
        with st.expander("💬 Commentaire"):
            st.write(job["comment"])
        with st.expander("Proposition de description de profile"):
            st.write(job["custom_profile"])
        # st.write(job["content"])
        # st.code(job["content"])
        st.markdown(job["content"].replace("\n", "<br>"), unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("⬅️ Précédent"):
                st.session_state.index = (st.session_state.index - 1) % total_jobs
                st.rerun()

        with col2:
            if st.button("Marquer comme lu ✅"):
                df.loc[df["link"] == job["link"], "is_read"] = 1
                save_data(df)
                st.rerun()

        with col3:
            if st.button("➡️ Suivant"):
                st.session_state.index = (st.session_state.index + 1) % total_jobs
                st.rerun()

        if st.button("📎 Postuler"):
            df.loc[df["link"] == job["link"], ["is_apply", "is_read"]] = 1
            save_data(df)
            st.rerun()

def offer_gpt_filter_page(df):
    st.title("📄 Offres non pertinentes")

    applied_jobs = df[(df["is_read"] == 0) & (df["is_good_offer"] == 0)] \
        .sort_values(by=["days_diff", "score"], ascending=[True, False]) \
        .reset_index(drop=True)

    if applied_jobs.empty:
        st.write("❌ Aucune offre filtrée")
    else:
        for index, job in applied_jobs.iterrows():
            col1, col2 = st.columns([0.85, 0.15])

            with col1:
                score = int(job["score"])
                color = get_color(score)
                st.markdown(f"""
                    <div style="margin: 20px 0; width: 100%; background-color: #eee; border-radius: 5px;">
                      <div style="width: {score}%; background-color: {color}; padding: 10px 0; border-radius: 5px; text-align: center; color: white; font-weight: bold;">
                        {score}%
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                st.write(
                    f"Publié il y a **{int(job['days_diff'])}** jours"
                    if pd.notna(job['days_diff'])
                    else "Date de publication non renseignée"
                )
                with st.expander(job["title"] + " | " + job["company"] + "\n" + job["comment"]):
                    st.write(job["content"])
                    st.markdown(f"[🔗 Lien vers l'offre]({job['link']})", unsafe_allow_html=True)

            with col2:
                # Bouton pour rétablir l'offre
                st.markdown("<div style='height: 85px;'></div>", unsafe_allow_html=True)
                if st.button("🔄 Restaurer", key=f"restore_{index}"):
                    df.loc[df["link"] == job["link"], "is_good_offer"] = 1
                    save_data(df)
                    st.rerun()

def offer_readed_page(df):
    st.title("📄 Offres déjà lu et non postulé")

    applied_jobs = df[(df["is_read"] == 1) & (df["is_apply"] == 0)].reset_index(drop=True)

    if applied_jobs.empty:
        st.write("❌ Aucun poste n'a été lu.")
    else:
        for index, job in applied_jobs.iterrows():
            col1, col2 = st.columns([0.9, 0.1])

            with col1:
                with st.expander(job["title"] + " | " + job["company"]):
                    st.write(job["content"])
                    st.markdown(f"[🔗 Lien vers l'offre]({job['link']})", unsafe_allow_html=True)

            with col2:
                # Bouton de suppression à droite
                if st.button("🔄 Restaurer", key=f"delete_{index}"):
                    df.loc[df["link"] == job["link"], ["is_apply", "is_read"]] = 0
                    save_data(df)
                    st.rerun()

def offer_refused_page(df):
    st.title("🚫 Candidatures refusées")

    refused_jobs = df[df["is_refused"] == 1].reset_index(drop=True)

    if refused_jobs.empty:
        st.write("✅ Aucun poste n'a été marqué comme refusé.")
    else:
        for index, job in refused_jobs.iterrows():
            col1, col2 = st.columns([0.9, 0.2])

            with col1:
                with st.expander(job["title"] + " | " + job["company"]):
                    st.write(job["content"])
                    st.markdown(f"[🔗 Lien vers l'offre]({job['link']})", unsafe_allow_html=True)

            with col2:
                # Bouton pour rétablir l'offre et enlever le statut "refusé"
                if st.button("🔄 Restaurer", key=f"restore_{index}"):
                    df.loc[df["link"] == job["link"], "is_refused"] = 0
                    save_data(df)
                    st.rerun()



def offer_applied_page(df):
    st.title("📄 Candidatures en cours")

    applied_jobs = df[(df["is_apply"] == 1) & (df["is_refused"] == 0)].reset_index(drop=True)

    if applied_jobs.empty:
        st.write("❌ Aucune candidature en cours.")
    else:
        for index, job in applied_jobs.iterrows():
            col1, col2, col3 = st.columns([0.8, 0.1, 0.2])

            with col1:
                with st.expander(job["title"] + " | " + job["company"]):
                    st.write(job["content"])
                    st.markdown(f"[🔗 Lien vers l'offre]({job['link']})", unsafe_allow_html=True)

            with col2:
                # Bouton de suppression à droite
                if st.button("🗑️", key=f"delete_{index}"):
                    df.loc[df["link"] == job["link"], ["is_apply", "is_read"]] = 0
                    save_data(df)
                    st.rerun()

            with col3:
                # Bouton pour marquer l'offre comme refusée
                if st.button("❌ Refusé", key=f"refused_{index}"):
                    df.loc[df["link"] == job["link"], "is_refused"] = 1
                    save_data(df)
                    st.rerun()