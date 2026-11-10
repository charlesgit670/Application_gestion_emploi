"""Cadre commun à toutes les pages : en-tête, menu latéral avec compteurs, mode sombre.

Usage dans une page :
    nav = page_frame("Offres", "/offres")   # construit l'en-tête et le menu
    ...contenu de la page...
    nav.refresh()                            # met à jour les compteurs après une action
"""
from nicegui import app, ui

from jobfinder.config import load_config
from jobfinder.ui import services

PRIMARY = "#2a78d6"

# (adresse, icône Material, libellé, clé du compteur affiché à droite)
NAV_ITEMS = [
    ("/", "space_dashboard", "Tableau de bord", None),
    ("/offres", "inbox", "Offres à traiter", "todo"),
    ("/candidatures", "send", "Candidatures", "active"),
    ("/scraping", "travel_explore", "Scraping & réglages", None),
]

GLOBAL_CSS = """
.job-description { white-space: pre-wrap; line-height: 1.55; }
.job-item.selected { background: rgba(42, 120, 214, 0.12); border-left: 3px solid #2a78d6; }
.kpi-value { font-size: 2rem; font-weight: 600; line-height: 1.1; }
/* fonds teintés semi-transparents : lisibles en mode clair comme en mode sombre */
.tint-primary { background: rgba(42, 120, 214, 0.12); }
.tint-warning { background: rgba(250, 178, 25, 0.16); }
"""


def page_frame(title: str, current_path: str):
    """Construit l'en-tête et le menu. Renvoie le menu (appeler .refresh() pour le mettre à jour)."""
    ui.colors(primary=PRIMARY)
    ui.add_css(GLOBAL_CSS)
    # Mode sombre mémorisé côté serveur (application locale, un seul utilisateur)
    dark = ui.dark_mode().bind_value(app.storage.general, "dark_mode")
    ui.page_title(f"{title} · JobFinder")

    with ui.header(elevated=False).classes("items-center px-4 py-2 bg-primary"):
        ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
        ui.label("JobFinder").classes("text-lg font-semibold")
        ui.label(f"· {title}").classes("text-lg opacity-80")
        ui.space()
        ui.button(icon="dark_mode", on_click=dark.toggle).props("flat round color=white").tooltip("Mode sombre")

    with ui.left_drawer(value=True, bordered=True).classes("p-0") as drawer:
        _nav_menu(current_path)
    return _nav_menu


@ui.refreshable
def _nav_menu(current_path: str) -> None:
    """Liens du menu avec le nombre d'offres de chaque liste."""
    numbers = services.counts(services.load_jobs(), load_config())
    with ui.list().classes("w-full"):
        for path, icon, label, count_key in NAV_ITEMS:
            item = ui.item(on_click=lambda p=path: ui.navigate.to(p)).classes("rounded-r-full mr-2")
            if path == current_path:
                item.classes("tint-primary text-primary")
            with item:
                with ui.item_section().props("avatar"):
                    ui.icon(icon)
                ui.item_section(label)
                if count_key:
                    with ui.item_section().props("side"):
                        ui.badge(str(numbers[count_key])).props("rounded color=primary")
        if services.scraping.running:
            with ui.item(on_click=lambda: ui.navigate.to("/scraping")):
                with ui.item_section().props("avatar"):
                    ui.spinner(size="sm")
                ui.item_section("Scraping en cours…").classes("text-primary")


# ---------------------------------------------------------------------------
# Petits éléments visuels réutilisés
# ---------------------------------------------------------------------------
def score_badge(score, threshold: int) -> None:
    """Pastille de score : verte si au-dessus du seuil, orange sinon, grise si non évaluée."""
    if score is None or score != score:  # None ou NaN/<NA>
        ui.badge("non évaluée").props("outline color=grey")
        return
    color = "positive" if score >= threshold else "orange-8"
    ui.badge(f"{int(score)} / 100").props(f"color={color}").tooltip(f"Seuil actuel : {threshold}")


def age_text(days) -> str:
    """« aujourd'hui », « il y a 3 j » ou « date inconnue »."""
    if days is None or days != days:
        return "date inconnue"
    days = int(days)
    return "aujourd'hui" if days <= 0 else f"il y a {days} j"
