import streamlit as st
import pandas as pd
import time

from app_utils import save_data
from JobColumns import JobColumns
from components.job_list_view import render_job_list_view_multi_action
from app_utils import ensure_data_loaded


st.title("💼 Suivi des Candidatures en Cours")

ensure_data_loaded()

if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    applied_jobs = df[(df[JobColumns.IS_APPLY] == 1) & (df[JobColumns.IS_REFUSED] == 0)].reset_index(drop=True)


    # --- FONCTIONS DE TRAITEMENT CORRECTES ET SECURISEES ---

    # Action de masse : Refuser toutes les candidatures de la sélection
    def mass_refuse(main_df, filtered_df):
        links = filtered_df[JobColumns.LINK].values
        main_df.loc[main_df[JobColumns.LINK].isin(links), JobColumns.IS_REFUSED] = 1
        st.success(f"Archivé : {len(links)} candidatures marquées comme refusées.")


    # Bouton individuel 🗑️ Annuler : Retire complètement du suivi (réinitialise)
    def handle_cancel_apply(main_df, current_job):
        mask = main_df[JobColumns.LINK] == current_job[JobColumns.LINK]
        # Assignations séquentielles pour forcer des types propres (pas de NaN)
        main_df.loc[mask, JobColumns.IS_APPLY] = 0
        main_df.loc[mask, JobColumns.IS_READ] = 0


    # Bouton individuel ❌ Refusé : Bascule l'offre vers l'historique des refus
    def handle_single_refuse(main_df, current_job):
        mask = main_df[JobColumns.LINK] == current_job[JobColumns.LINK]
        main_df.loc[mask, JobColumns.IS_REFUSED] = 1


    render_job_list_view_multi_action(
        df=df,
        filtered_df=applied_jobs,
        empty_message="Vous n'avez aucune candidature active listée. C'est le moment d'envoyer des CV !",
        total_label="Suivi de **{}** candidature(s) active(s)",
        expander_title_fn=lambda job: f"📩 {job[JobColumns.TITLE]} — {job[JobColumns.COMPANY]}",
        button_configs=[
            {
                "label": "🗑️ Annuler",
                "key_prefix": "del_",
                "help_text": "Retirer du suivi",
                "col_ratio": 0.15,
                "handler": handle_cancel_apply,  # Utilisation de la fonction corrigée
            },
            {
                "label": "❌ Refusé",
                "key_prefix": "ref_",
                "help_text": "Marquer comme refusé",
                "col_ratio": 0.15,
                "handler": handle_single_refuse,  # Utilisation de la fonction corrigée
            },
        ],
        page_key="p6_page",
        items_per_page=10,
        content_preview_length=1500,
        extra_top_buttons=[
            {
                "label": "💥 Tout marquer comme Refusé",
                "type": "primary",
                "help": "Bascule toutes les candidatures en cours vers l'historique des refus",
                "success_msg": f"{len(applied_jobs)} candidatures archivées.",
                "handler": mass_refuse,
            },
        ],
    )
else:
    st.warning("Aucune donnée disponible.")