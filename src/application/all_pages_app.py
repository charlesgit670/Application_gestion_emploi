import streamlit as st
import threading
import time
import pandas as pd

from main import update_store_data


def save_data(df, data_file="data/job.csv"):
    df.to_csv(data_file, sep=";", index=False)

def get_color(score):
    r = int(255 - (score * 2.55))
    g = int(score * 2.55)
    return f"rgb({r},{g},0)"


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
            update_store_data(progress_dict, True, True)

        progress_dict = st.session_state.progress_dict
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

        st.success("🎉 Scraping terminé !")

        # Réinitialisation des états
        st.session_state.scraping_running = False
        st.session_state.launch_clicked = False
        st.session_state.scraping_started = False


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
                if st.button("🗑️", key=f"delete_{index}"):
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