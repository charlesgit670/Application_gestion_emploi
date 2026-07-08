import streamlit as st
import pandas as pd
import plotly.express as px

from JobColumns import JobColumns
from app_utils import ensure_data_loaded

st.set_page_config(
    page_title="Job Tracker & Scraper",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)


ensure_data_loaded()

st.title("💼 Assistant de Recherche d'Emploi Intelligent")
st.write("---")

if not st.session_state["df"].empty:
    # --- MAPPING POUR UN AFFICHAGE PROPRE DES PLATFORMES ---
    platform_labels = {
        "wttj": "Welcome To The Jungle",
        "apec": "APEC",
        "linkedin": "LinkedIn",
        "sp": "Service Public",
        "hw": "HelloWork",
        "ft": "France Travail",
        "Autre": "Autre / Inconnu"
    }

    # --- PALETTE DE COULEURS CLAIRES ET PASTELS PAR PLATFORME ---
    platform_colors = {
        "Welcome To The Jungle": "#FFE57F",  # Jaune pastel nhẹ
        "APEC": "#76DEED",  # Cyan clair pastel
        "LinkedIn": "#7FBCE5",  # Bleu clair pastel
        "Service Public": "#FFA4A2",  # Rouge/Rose pastel
        "HelloWork": "#FFAB91",  # Corail doux pastel
        "France Travail": "#9FA8DA",  # Bleu-violet doux pastel
        "Autre / Inconnu": "#CFD8DC"  # Gris clair pastel
    }

    # Préparer un dataframe propre avec des noms lisibles
    df_clean = st.session_state["df"].copy()
    df_clean[JobColumns.PLATFORM] = df_clean[JobColumns.PLATFORM].fillna("Autre")
    df_clean["Nom_Plateforme"] = df_clean[JobColumns.PLATFORM].map(platform_labels).fillna(
        df_clean[JobColumns.PLATFORM])

    # --- 1. INTERVALLE TEMPOREL DES DONNÉES ---
    valid_dates = df_clean[df_clean[JobColumns.DATE].notna()]
    if not valid_dates.empty:
        min_date = valid_dates[JobColumns.DATE].min().strftime("%d/%m/%Y")
        max_date = valid_dates[JobColumns.DATE].max().strftime("%d/%m/%Y")
        st.info(f"📅 **Intervalle temporel des données affichées :** du **{min_date}** au **{max_date}**")
    else:
        st.warning("⚠️ Aucune date de publication valide détectée dans les données.")

    # Calculs des métriques principales (KPI)
    total_offres = len(df_clean)
    a_lire = len(df_clean[(df_clean[JobColumns.IS_READ] == 0) & (df_clean[JobColumns.IS_GOOD_OFFER] == 1)])
    en_cours = len(df_clean[(df_clean[JobColumns.IS_APPLY] == 1) & (df_clean[JobColumns.IS_REFUSED] == 0)])
    total_refus = len(df_clean[df_clean[JobColumns.IS_REFUSED] == 1])
    ecartees_ia = len(df_clean[(df_clean[JobColumns.IS_READ] == 0) & (df_clean[JobColumns.IS_GOOD_OFFER] == 0)])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total d'offres collectées", total_offres)
    col2.metric("Nouvelles offres à analyser", a_lire, delta=f"{a_lire} urgentes", delta_color="inverse")
    col3.metric("Candidatures en cours", en_cours)

    st.write("---")
    st.subheader("📊 Statistiques de votre Marché")

    # =========================================================================
    # --- LIGNE 1 : ENTONNOIR (GAUCHE) & REPARTITION DES OFFRES (DROITE) ---
    # =========================================================================
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.markdown("##### 🎯 Évolution globale de vos démarches (Entonnoir)")
        steps_data = pd.DataFrame({
            "Étape": ["1. Offres Scrapées", "2. Validées par l'IA", "3. Postulées", "4. En Cours"],
            "Volume": [total_offres, (total_offres - ecartees_ia), (en_cours + total_refus), en_cours]
        })
        fig_funnel = px.bar(
            steps_data,
            x="Volume",
            y="Étape",
            orientation="h",
            text="Volume",
            color="Étape",
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        fig_funnel.update_layout(showlegend=False, height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_funnel, use_container_width=True)

    with row1_col2:
        st.markdown("##### 🌐 Volume total d'offres par Plateforme")
        platform_counts = df_clean["Nom_Plateforme"].value_counts().reset_index()
        platform_counts.columns = ["Plateforme", "Nombre"]

        fig_pie = px.pie(
            platform_counts,
            values="Nombre",
            names="Plateforme",
            hole=0.4,
            color="Plateforme",
            color_discrete_map=platform_colors
        )
        fig_pie.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.write("---")

    # =========================================================================
    # --- LIGNE 2 : TAUX D'ACCEPTATION (GAUCHE) & INTENSITÉ TEMPORELLE (DROITE) ---
    # =========================================================================
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.markdown("##### 📈 Taux de pertinence (IA) après filtrage par Plateforme")

        # Agrégation des taux de validation
        platform_summary = df_clean.groupby("Nom_Plateforme").agg(
            Total_Offres=(JobColumns.LINK, "count"),
            Offres_Valides=(JobColumns.IS_GOOD_OFFER, lambda x: (x == 1).sum())
        ).reset_index()

        platform_summary["Pourcentage"] = (
                    platform_summary["Offres_Valides"] / platform_summary["Total_Offres"] * 100).round(1)

        # Classement décroissant (les plus grands pourcentages en haut)
        # Plotly Express affiche le haut du DataFrame en bas de l'axe Y pour les barres horizontales,
        # on trie donc par ordre croissant pour obtenir un affichage visuel décroissant de haut en bas.
        platform_summary = platform_summary.sort_values(by="Pourcentage", ascending=False)

        fig_rate = px.bar(
            platform_summary,
            x="Pourcentage",
            y="Nom_Plateforme",
            orientation="h",
            text=platform_summary["Pourcentage"].apply(lambda x: f"{x}%"),
            labels={"Nom_Plateforme": "Plateforme", "Pourcentage": "Offres Validées par l'IA (%)"},
            color="Nom_Plateforme",
            color_discrete_map=platform_colors,
            hover_data=["Total_Offres", "Offres_Valides"]
        )
        fig_rate.update_layout(showlegend=False, height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_rate, use_container_width=True)

    with row2_col2:
        st.markdown("##### 📅 Intensité du marché (Volume d'offres publiées)")

        if not valid_dates.empty:
            df_timeline = valid_dates.copy()

            time_grain = st.radio(
                "Regrouper par :",
                options=["Jour", "Semaine", "Mois"],
                index=0,
                horizontal=True,
                key="timeline_grain_selector"
            )

            if time_grain == "Jour":
                df_timeline["Periode"] = df_timeline[JobColumns.DATE].dt.date
                title_x = "Date de publication (Jour)"
            elif time_grain == "Semaine":
                df_timeline["Periode"] = df_timeline[JobColumns.DATE].dt.to_period("W").dt.start_time
                title_x = "Semaine de publication (Lundi)"
            else:
                df_timeline["Periode"] = df_timeline[JobColumns.DATE].dt.to_period("M").dt.start_time
                title_x = "Mois de publication"

            timeline_counts = df_timeline["Periode"].value_counts().sort_index().reset_index()
            timeline_counts.columns = ["Période", "Offres Publiées"]

            fig_line = px.line(
                timeline_counts,
                x="Période",
                y="Offres Publiées",
                markers=True,
                color_discrete_sequence=["#e67e22"],
                labels={"Période": title_x, "Offres Publiées": "Nombre d'offres"}
            )
            fig_line.update_layout(height=250, margin=dict(l=20, r=20, t=10, b=20))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Données temporelles insuffisantes pour afficher l'évolution.")

else:
    st.info("Aucune donnée disponible. Rendez-vous sur la page de Scraping pour collecter vos premières offres.")