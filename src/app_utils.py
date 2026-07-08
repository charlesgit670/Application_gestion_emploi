import pandas as pd
import json
import streamlit as st
import os
from datetime import datetime, timezone

from JobColumns import JobColumns

CONFIG_FILE = "config.json"
DATA_FILE = "data/job.csv"

def save_data(df, data_file="data/job.csv"):
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    df.to_csv(data_file, sep=";", index=False, encoding="utf-8")

def get_color(score):
    r = int(255 - (score * 2.55))
    g = int(score * 2.55)
    return f"rgb({r},{g},0)"

@st.cache_data(ttl=60)
def load_data(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, sep=";", encoding="utf-8")
            # Conversion en datetime sans fuseau horaire pour les calculs internes
            df[JobColumns.DATE] = pd.to_datetime(df[JobColumns.DATE], errors="coerce").dt.tz_localize(None)

            # Calcul de la différence de jours
            today = pd.Timestamp(datetime.now(timezone.utc).date()).tz_localize(None)
            df[JobColumns.DAYS_DIFF] = (today - df[JobColumns.DATE]).dt.days
            return df
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier CSV : {e}")

    # Initialisation robuste typée
    return pd.DataFrame(columns=[
        JobColumns.TITLE, JobColumns.CONTENT, JobColumns.COMPANY, JobColumns.LINK,
        JobColumns.PLATFORM, JobColumns.DATE, JobColumns.IS_READ, JobColumns.IS_APPLY,
        JobColumns.IS_REFUSED, JobColumns.IS_GOOD_OFFER, JobColumns.COMMENT,
        JobColumns.SCORE, JobColumns.CUSTOM_PROFILE, JobColumns.DAYS_DIFF
    ])


def ensure_data_loaded():
    """
    Garantit que le DataFrame est présent en mémoire.
    Ne recharge rien si les données sont déjà là.
    """
    if "df" not in st.session_state or st.session_state["df"] is None or st.session_state["df"].empty:
        st.session_state["df"] = load_data(DATA_FILE)