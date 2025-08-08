import streamlit as st
import pandas as pd
import os
from datetime import datetime

from application.all_pages_app import scrapping_page, new_offer_page, offer_gpt_filter_page, offer_readed_page, offer_applied_page, offer_refused_page

# Charger ou initialiser le dataframe
DATA_FILE = "data/job.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE, sep=";")
        df["date"] = pd.to_datetime(df["date"])

        today = pd.Timestamp(datetime.utcnow().date())
        df["days_diff"] = (today - df["date"]).dt.days

        return df
    else:
        return pd.DataFrame(columns=["title", "content", "company", "link", "date", "is_read", "is_apply", "is_refused", "is_good_offer", "comment", "score", "custom_profile", "days_diff"])


df = load_data()

# Initialiser session state pour la navigation
if "index" not in st.session_state:
    st.session_state.index = 0

# Navigation entre pages
st.sidebar.title("Navigation")
page = st.sidebar.radio("Aller à :", ["Mettre à jour les offres", "Nouvelles offres d'emploi", "Offres filtrées par GPT", "Offres déjà lu", "Candidatures refusés", "Candidatures en cours"])

# Page permettant de scrap les nouvelles offres
if page == "Mettre à jour les offres":
    scrapping_page()

# Page d'accueil - Affiche les offres non lues
if page == "Nouvelles offres d'emploi":
    new_offer_page(df)

# Offre filtrer par LLM
elif page == "Offres filtrées par GPT":
    offer_gpt_filter_page(df)

# Page des postes déjà lu
elif page == "Offres déjà lu":
    offer_readed_page(df)

# Page des postes refusés
elif page == "Candidatures refusés":
    offer_refused_page(df)


# Page des postes postulés
elif page == "Candidatures en cours":
    offer_applied_page(df)



