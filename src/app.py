import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone
# Import de la classe de validation des colonnes
from JobColumns import JobColumns

st.set_page_config(
    page_title="Job Tracker & Scraper",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_FILE = "data/job.csv"

@st.cache_data(ttl=60)
def load_data(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, sep=";", encoding="utf-8")
            df[JobColumns.DATE] = pd.to_datetime(df[JobColumns.DATE], errors="coerce")

            today = pd.Timestamp(datetime.now(timezone.utc).date())
            df[JobColumns.DAYS_DIFF] = (today - df[JobColumns.DATE].dt.tz_localize(None)).dt.days
            return df
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier CSV : {e}")

    # Initialisation robuste typée
    return pd.DataFrame(columns=[
        JobColumns.TITLE, JobColumns.CONTENT, JobColumns.COMPANY, JobColumns.LINK,
        JobColumns.DATE, JobColumns.IS_READ, JobColumns.IS_APPLY, JobColumns.IS_REFUSED,
        JobColumns.IS_GOOD_OFFER, JobColumns.COMMENT, JobColumns.SCORE,
        JobColumns.CUSTOM_PROFILE, JobColumns.DAYS_DIFF
    ])

df = load_data(DATA_FILE)
st.session_state["df"] = df

st.title("💼 Assistant de Recherche d'Emploi Intelligent")
st.write("---")

if not df.empty:
    total_offres = len(df)
    a_lire = len(df[(df[JobColumns.IS_READ] == 0) & (df[JobColumns.IS_GOOD_OFFER] == 1)])
    en_cours = len(df[(df[JobColumns.IS_APPLY] == 1) & (df[JobColumns.IS_REFUSED] == 0)])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total d'offres collectées", total_offres)
    col2.metric("Nouvelles offres à analyser", a_lire, delta=f"{a_lire} urgentes", delta_color="inverse")
    col3.metric("Candidatures en cours", en_cours)
else:
    st.info("Aucune donnée disponible. Rendez-vous sur la page de Scraping pour collecter vos premières offres.")