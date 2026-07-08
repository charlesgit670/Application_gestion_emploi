import streamlit as st
import pandas as pd
import time

from app_utils import save_data, get_color
from JobColumns import JobColumns
from app_utils import ensure_data_loaded

st.title("📌 Nouvelles Offres Validées")

ensure_data_loaded()

if "df" not in st.session_state or st.session_state["df"].empty:
    st.warning("Aucune donnée disponible. Veuillez d'abord exécuter un scraping.")
else:
    df = st.session_state["df"]

    # --- MANAGEMENT DU FILTRE TEMPOREL DANS LA SIDEBAR ---
    st.sidebar.header("⏳ Filtre Temporel")
    use_date_filter = st.sidebar.checkbox("Activer le filtre par ancienneté", value=True)

    max_days = 90
    if use_date_filter:
        max_days = st.sidebar.slider(
            "Afficher les offres publiées il y a moins de (jours) :",
            min_value=0,
            max_value=90,
            value=7,
            step=1
        )

    # Filtrage initial de base (Non lues + Validées positives par l'IA)
    unread_jobs = df[(df[JobColumns.IS_READ] == 0) & (df[JobColumns.IS_GOOD_OFFER] == 1)]

    # Application du filtre du Slider si la case est cochée
    if use_date_filter:
        unread_jobs = unread_jobs[unread_jobs[JobColumns.DAYS_DIFF] <= max_days]

    # Tri et réinitialisation de l'index
    unread_jobs = unread_jobs.sort_values(by=[JobColumns.DAYS_DIFF, JobColumns.SCORE], ascending=[True, False]) \
        .reset_index(drop=True)

    if unread_jobs.empty:
        if use_date_filter:
            st.success(f"✅ Aucune nouvelle offre pertinente sur les {max_days} derniers jours !")
        else:
            st.success("✅ Toutes les nouvelles offres pertinentes ont été traitées !")
    else:
        # Message de description dynamique selon le filtre
        if use_date_filter:
            st.write(
                f"Il y a actuellement **{len(unread_jobs)}** nouvelles offres datant de moins de **{max_days} jours**.")
        else:
            st.write(f"Il y a actuellement **{len(unread_jobs)}** nouvelles offres au total (filtre désactivé).")

        if st.button("🧹 Tout marquer comme lu", type="secondary"):
            links_to_update = unread_jobs[JobColumns.LINK].values
            df.loc[df[JobColumns.LINK].isin(links_to_update), JobColumns.IS_READ] = 1
            save_data(df)
            st.cache_data.clear()
            st.success(f"🎉 {len(links_to_update)} offres ont été marquées comme lues !")
            time.sleep(1)
            st.rerun()

        st.write("---")

        if "card_index" not in st.session_state:
            st.session_state.card_index = 0

        current_index = st.session_state.card_index % len(unread_jobs)
        job = unread_jobs.iloc[current_index]

        st.subheader(f"Annonce {current_index + 1} sur {len(unread_jobs)}")
        st.header(job[JobColumns.TITLE])
        st.subheader(f"🏢 {job[JobColumns.COMPANY]}")

        days = job[JobColumns.DAYS_DIFF]
        st.write(f"📅 Publiée il y a **{int(days)}** jours" if pd.notna(days) else "Date non spécifiée")

        col_analysis, col_profile = st.columns(2)
        with col_analysis:

            score = int(job[JobColumns.SCORE]) if pd.notna(job[JobColumns.SCORE]) else -1
            if score != -1:
                color = get_color(score)
                st.markdown(f"""
                   <div style="margin: 15px 0; width: 100%; background-color: #eee; border-radius: 5px;">
                     <div style="width: {score}%; background-color: {color}; padding: 8px 0; border-radius: 5px; text-align: center; color: white; font-weight: bold;">
                       Correspondance IA : {score}%
                     </div>
                   </div>
                   """, unsafe_allow_html=True)



            with st.expander("💬 Commentaire de pertinence IA", expanded=True):
                st.write(
                    job[JobColumns.COMMENT] if pd.notna(job[JobColumns.COMMENT]) else "Aucun commentaire disponible.")
        with col_profile:
            custom_prof = job.get(JobColumns.CUSTOM_PROFILE)
            if pd.notna(custom_prof) and str(custom_prof).strip():
                with st.expander("👤 Objectif CV adapté au poste", expanded=True):
                    st.write(custom_prof)

        st.markdown("### 📄 Descriptif de l'offre")

        # Préparation de la string en amont pour éviter l'erreur de backslash dans le bloc de texte f-string
        job_content_html = str(job[JobColumns.CONTENT]).replace("\n", "<br>")
        st.markdown(job_content_html, unsafe_allow_html=True)
        st.markdown(f"[🔗 Ouvrir le lien d'origine]({job[JobColumns.LINK]})")

        st.write("---")
        b_prev, b_read, b_apply, b_next = st.columns(4)

        with b_prev:
            if st.button("⬅️ Précédent"):
                st.session_state.card_index = (st.session_state.card_index - 1) % len(unread_jobs)
                st.rerun()
        with b_read:
            if st.button("Marquer comme lu ✅", key="btn_read_single"):
                df.loc[df[JobColumns.LINK] == job[JobColumns.LINK], JobColumns.IS_READ] = 1
                save_data(df)
                st.cache_data.clear()
                st.rerun()
        with b_apply:
            if st.button("📎 Postuler (Suivi en cours)", key="btn_apply_single"):
                df.loc[df[JobColumns.LINK] == job[JobColumns.LINK], [JobColumns.IS_APPLY, JobColumns.IS_READ]] = 1
                save_data(df)
                st.cache_data.clear()
                st.rerun()
        with b_next:
            if st.button("➡️ Suivant"):
                st.session_state.card_index = (st.session_state.card_index + 1) % len(unread_jobs)
                st.rerun()