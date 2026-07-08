import streamlit as st
import pandas as pd
from JobColumns import JobColumns
from components.job_list_view import render_job_list_view
from app_utils import ensure_data_loaded

st.title("❌ Candidatures Refusées")

ensure_data_loaded()

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    refused_jobs = df[df[JobColumns.IS_REFUSED] == 1].reset_index(drop=True)


    # CORRECTION SÉCURISÉE ET EXPLICITE : Évite les NaN et remet les bons statuts
    def handle_reactivate(main_df, current_job):
        mask = main_df[JobColumns.LINK] == current_job[JobColumns.LINK]

        # 1. On retire le statut refusé
        main_df.loc[mask, JobColumns.IS_REFUSED] = 0
        # 2. On s'assure qu'elle redevienne active dans le suivi des candidatures (is_apply = 1)
        main_df.loc[mask, JobColumns.IS_APPLY] = 1
        main_df.loc[mask, JobColumns.IS_READ] = 1


    render_job_list_view(
        df=df,
        filtered_df=refused_jobs,
        empty_message="Aucun refus à déplorer pour le moment. Gardez le cap ! 👍",
        total_label="Total de refus listés :",
        expander_title_fn=lambda job: f"🚫 {job[JobColumns.TITLE]} chez {job[JobColumns.COMPANY]}",
        button_config={
            "label": "🔄 Réactiver",
            "key_prefix": "unrefuse_",
            "help_text": "Retourner la candidature dans celles en cours",
            "handler": handle_reactivate,  # Utilisation de la fonction corrigée
        },
        page_key="p5_page",
        items_per_page=10,
    )
else:
    st.warning("Aucune donnée disponible.")