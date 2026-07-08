import streamlit as st
import pandas as pd

from JobColumns import JobColumns
from components.job_list_view import render_job_list_view
from app_utils import ensure_data_loaded

st.title("✅ Historique des offres lues (Non postulées)")

ensure_data_loaded()

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    read_jobs = df[(df[JobColumns.IS_READ] == 1) & (df[JobColumns.IS_APPLY] == 0)].reset_index(drop=True)


    # CORRECTION ROBUSTE : Assignation colonne par colonne pour bloquer les NaN
    def handle_reset(main_df, current_job):
        # On crée le masque pour cibler la bonne ligne
        mask = main_df[JobColumns.LINK] == current_job[JobColumns.LINK]

        # On force les valeurs une par une de manière séquentielle
        main_df.loc[mask, JobColumns.IS_APPLY] = 0
        main_df.loc[mask, JobColumns.IS_READ] = 0

    render_job_list_view(
        df=df,
        filtered_df=read_jobs,
        empty_message="Aucun historique disponible.",
        total_label="Total d'offres lues :",
        expander_title_fn=lambda job: f"{job[JobColumns.TITLE]} | {job[JobColumns.COMPANY]}",
        button_config={
            "label": "🔄 Réétudier",
            "key_prefix": "reset_",
            "help_text": "Retourner l'offre dans les nouvelles offres à analyser",
            "handler": handle_reset,
        },
        page_key="p4_page",
        items_per_page=10,
    )
else:
    st.warning("Aucune donnée disponible.")