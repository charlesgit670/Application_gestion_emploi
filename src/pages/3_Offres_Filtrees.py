import streamlit as st
import pandas as pd

from JobColumns import JobColumns
from components.job_list_view import render_job_list_view
from app_utils import ensure_data_loaded

st.title("🤖 Offres écartées automatiquement par l'IA")

ensure_data_loaded()

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    bad_jobs = df[(df[JobColumns.IS_READ] == 0) & (df[JobColumns.IS_GOOD_OFFER] == 0)].reset_index(drop=True)

    # Fonction de traitement propre pour la réhabilitation
    def handle_restore(main_df, current_job):
        main_df.loc[main_df[JobColumns.LINK] == current_job[JobColumns.LINK], JobColumns.IS_GOOD_OFFER] = 1

    render_job_list_view(
        df=df,
        filtered_df=bad_jobs,
        empty_message="Aucune offre n'a été filtrée négativement par le LLM.",
        total_label="Total d'offres filtrées :",
        expander_title_fn=lambda job: (
            f"**[{int(job[JobColumns.SCORE]) if pd.notna(job[JobColumns.SCORE]) else 0}%]** "
            f"{job[JobColumns.TITLE]} — *{job[JobColumns.COMPANY]}*"
        ),
        button_config={
            "label": "🔄 Réhabiliter",
            "key_prefix": "restore_",
            "help_text": "Remettre l'offre dans les nouvelles offres validées",
            "handler": handle_restore, # Utilisation de la fonction corrigée
        },
        page_key="p3_page",
        items_per_page=10,
    )
else:
    st.warning("Aucune donnée disponible. Veuillez d'abord exécuter un scraping.")