import streamlit as st
import pandas as pd
import os

# Charger ou initialiser le dataframe
DATA_FILE = "data/job.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE, sep=";")
    else:
        return pd.DataFrame(columns=["title", "content", "company", "link", "is_read", "is_apply", "is_refused"])

def save_data(df):
    df.to_csv(DATA_FILE, sep=";", index=False)

df = load_data()

# Initialiser session state pour la navigation
if "index" not in st.session_state:
    st.session_state.index = 0

# Navigation entre pages
st.sidebar.title("Navigation")
page = st.sidebar.radio("Aller à :", ["Nouvelles offres d'emploi", "Offres déjà lu", "Candidatures refusés", "Candidatures en cours"])

# Page d'accueil - Affiche les offres non lues
if page == "Nouvelles offres d'emploi":
    # Filtrer les offres non lues
    unread_jobs = df[df["is_read"] == 0].reset_index(drop=True)

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

# Page des postes déjà lu
elif page == "Offres déjà lu":
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

# Page des postes refusés
elif page == "Candidatures refusés":
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


# Page des postes postulés
elif page == "Candidatures en cours":
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



