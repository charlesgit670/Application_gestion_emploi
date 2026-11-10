"""Page d'accueil : indicateurs, relances à faire et graphiques du marché.

Choix des graphiques :
    - Entonnoir     : barres horizontales, un seul bleu en dégradé ordonné (étapes successives)
    - Plateformes   : barres empilées « à traiter / écartées » par plateforme (2 séries, légende)
    - Publications  : courbe hebdomadaire (une seule série, pas de légende)
Les fonds sont transparents et les textes gris neutres : lisibles en mode clair et sombre.
"""
import pandas as pd
import plotly.graph_objects as go
from nicegui import ui

from jobfinder.config import load_config
from jobfinder.models import PLATFORM_LABELS, Col, Status, is_rejected_by_ai
from jobfinder.ui import services
from jobfinder.ui.layout import page_frame

# Couleurs (palette catégorielle de référence, ordre fixe) et encre neutre
BLUE, ORANGE = "#2a78d6", "#eb6834"
FUNNEL_BLUES = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab"]  # dégradé ordonné clair -> foncé
MUTED_INK, GRID = "#898781", "rgba(137, 135, 129, 0.25)"


def base_layout(fig: go.Figure, height: int = 300) -> go.Figure:
    """Mise en forme commune : fond transparent, grille discrète, marges serrées."""
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=MUTED_INK, size=12),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def funnel_figure(df: pd.DataFrame, threshold: int) -> go.Figure:
    stats = services.application_stats(df)
    steps = {
        "Offres collectées": len(df),
        "Jugées pertinentes": int((~is_rejected_by_ai(df, threshold)).sum()),
        "Candidatures": stats["sent"],
        "Avec entretien": stats["with_interview"],
    }
    fig = go.Figure(go.Bar(
        x=list(steps.values()), y=list(steps.keys()), orientation="h",
        marker=dict(color=FUNNEL_BLUES, cornerradius=4),
        text=[f"{v:,}".replace(",", " ") for v in steps.values()], textposition="outside",
        hovertemplate="%{y} : %{x}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    # Marge à droite pour que les étiquettes de valeur ne soient pas coupées
    fig.update_xaxes(range=[0, max(steps.values()) * 1.18], showticklabels=False, showgrid=False)
    return base_layout(fig, 260)


def platform_figure(df: pd.DataFrame, threshold: int) -> go.Figure:
    new = df[df[Col.STATUS] == Status.NOUVELLE]
    rejected = is_rejected_by_ai(new, threshold)
    table = pd.DataFrame({
        "À traiter": new[~rejected].groupby(Col.PLATFORM).size(),
        "Écartées": new[rejected].groupby(Col.PLATFORM).size(),
    }).fillna(0).astype(int)
    table = table.assign(total=table.sum(axis=1)).sort_values("total")
    labels = [PLATFORM_LABELS.get(k, k) for k in table.index]

    fig = go.Figure()
    for column, color in (("À traiter", BLUE), ("Écartées", ORANGE)):
        fig.add_bar(y=labels, x=table[column], name=column, orientation="h",
                    marker=dict(color=color, line=dict(width=2, color="rgba(0,0,0,0)")),
                    hovertemplate=f"%{{y}} · {column} : %{{x}}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35,
                      legend=dict(orientation="h", y=1.08, x=0, font=dict(color=MUTED_INK)))
    return base_layout(fig)


def relevance_figure(df: pd.DataFrame, threshold: int) -> go.Figure:
    """Taux de pertinence IA par plateforme : une seule mesure, donc une seule couleur."""
    table = services.relevance_by_platform(df, threshold)
    labels = [PLATFORM_LABELS.get(k, k) for k in table.index]
    fig = go.Figure(go.Bar(
        x=table["percent"], y=labels, orientation="h",
        marker=dict(color=BLUE, cornerradius=4),
        text=[f"{p:.0f} %" for p in table["percent"]], textposition="outside",
        customdata=table[["relevant", "evaluated"]].astype(int).values,
        hovertemplate="%{y} : %{x:.1f} % (%{customdata[0]} / %{customdata[1]} offres évaluées)<extra></extra>",
    ))
    fig.update_xaxes(range=[0, max(table["percent"].max() * 1.2, 10)], ticksuffix=" %")
    fig.update_yaxes(showgrid=False)
    return base_layout(fig)


def timeline_figure(df: pd.DataFrame) -> go.Figure:
    dated = df.dropna(subset=[Col.PUBLISHED_ON])
    weekly = dated.groupby(dated[Col.PUBLISHED_ON].dt.to_period("W").dt.start_time).size().tail(26)
    fig = go.Figure(go.Scatter(
        x=weekly.index, y=weekly.values, mode="lines+markers",
        line=dict(color=BLUE, width=2), marker=dict(size=8, color=BLUE),
        hovertemplate="Semaine du %{x|%d/%m/%Y} : %{y} offres<extra></extra>",
    ))
    return base_layout(fig)


def kpi_tile(label: str, value: int, icon: str, target: str, accent: str = "text-primary") -> None:
    with ui.card().classes("cursor-pointer min-w-[11rem] grow").on("click", lambda: ui.navigate.to(target)):
        with ui.row().classes("items-center gap-2 text-grey-7"):
            ui.icon(icon)
            ui.label(label)
        ui.label(f"{value:,}".replace(",", " ")).classes(f"kpi-value {accent}")


def application_stats_card(stats: dict) -> None:
    """Chiffres clés des candidatures : volume, entretiens, taux d'entretien, refus."""
    figures = [
        ("Candidatures envoyées", str(stats["sent"]), "send"),
        ("Avec au moins un entretien", str(stats["with_interview"]), "record_voice_over"),
        ("Taux d'entretien", f"{stats['interview_rate']:.0%}".replace("%", " %"), "percent"),
        ("Entretiens réalisés", str(stats["interviews"]), "event_available"),
        ("Refus", f"{stats['refused']}  (dont {stats['refused_after_interview']} après entretien)", "block"),
        ("En attente de réponse", str(stats["waiting"]), "hourglass_empty"),
    ]
    with ui.card().classes("w-full"):
        ui.label("Suivi des candidatures").classes("text-subtitle1 font-medium")
        with ui.grid(columns="repeat(auto-fit, minmax(180px, 1fr))").classes("w-full gap-4"):
            for label, value, icon in figures:
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-1 text-grey-7 text-caption"):
                        ui.icon(icon, size="xs")
                        ui.label(label)
                    ui.label(value).classes("text-h6 font-medium")


@ui.page("/")
def dashboard_page() -> None:
    page_frame("Tableau de bord", "/")
    config = load_config()
    df = services.load_jobs()
    numbers = services.counts(df, config)
    threshold = config.llm.score_threshold

    if df.empty:
        with ui.card().classes("w-full items-center q-pa-xl"):
            ui.icon("travel_explore", size="xl", color="primary")
            ui.label("Aucune offre pour l'instant.").classes("text-h6")
            ui.button("Configurer et lancer un scraping", on_click=lambda: ui.navigate.to("/scraping"))
        return

    with ui.row().classes("w-full gap-4"):
        kpi_tile("À traiter", numbers["todo"], "inbox", "/offres")
        kpi_tile("Candidatures en cours", numbers["active"], "send", "/candidatures")
        kpi_tile("Relances à faire", numbers["follow_up"], "notifications_active", "/candidatures",
                 "text-orange-9" if numbers["follow_up"] else "text-primary")
        kpi_tile("Écartées", numbers["rejected"], "filter_alt_off", "/offres", "text-grey-8")

    application_stats_card(services.application_stats(df))

    follow_ups = services.needs_follow_up(df, config.follow_up_days)
    if not follow_ups.empty:
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("notifications_active", color="orange-9")
                ui.label(f"Relances à faire (sans nouvelle depuis {config.follow_up_days} jours ou plus)") \
                    .classes("text-subtitle1 font-medium")
            with ui.list().props("dense separator").classes("w-full"):
                for row in follow_ups.head(8).itertuples():
                    with ui.item(on_click=lambda: ui.navigate.to("/candidatures")):
                        with ui.item_section():
                            ui.item_label(f"{row.title} — {row.company}")
                        with ui.item_section().props("side"):
                            ui.label(f"{int(row.days_waiting)} j")

    with ui.grid(columns="repeat(auto-fit, minmax(420px, 1fr))").classes("w-full gap-4"):
        with ui.card():
            ui.label("Entonnoir de recherche").classes("text-subtitle1 font-medium")
            ui.plotly(funnel_figure(df, threshold)).classes("w-full")
        with ui.card():
            ui.label(f"Taux de pertinence IA par plateforme (score ≥ {threshold})") \
                .classes("text-subtitle1 font-medium")
            ui.plotly(relevance_figure(df, threshold)).classes("w-full")
        with ui.card():
            ui.label("Offres nouvelles par plateforme").classes("text-subtitle1 font-medium")
            ui.plotly(platform_figure(df, threshold)).classes("w-full")
        with ui.card():
            ui.label("Offres publiées par semaine (6 derniers mois)").classes("text-subtitle1 font-medium")
            ui.plotly(timeline_figure(df)).classes("w-full")

    span = df[Col.PUBLISHED_ON].dropna()
    if not span.empty:
        ui.label(f"{numbers['total']:,} offres en base, publiées du {span.min():%d/%m/%Y} au {span.max():%d/%m/%Y}."
                 .replace(",", " ")).classes("text-caption text-grey-7")
