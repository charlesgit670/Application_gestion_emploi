"""Page « Offres » : trier les nouvelles offres, revoir les écartées et les offres lues.

Raccourcis clavier : ← / → offre précédente / suivante, L = lue, P = postuler,
R = réhabiliter (offres écartées) ou remettre à traiter (offres lues).
"""
import pandas as pd
from nicegui import ui

from jobfinder.config import load_config, save_config
from jobfinder.models import PLATFORM_LABELS, Col, Status
from jobfinder.ui import services
from jobfinder.ui.job_browser import Action, JobBrowser
from jobfinder.ui.layout import page_frame

AGE_OPTIONS = {0: "Toutes les dates", 3: "Moins de 3 jours", 7: "Moins de 7 jours",
               14: "Moins de 14 jours", 30: "Moins de 30 jours"}


@ui.page("/offres")
def offers_page() -> None:
    nav = page_frame("Offres", "/offres")
    config = load_config()
    state = {"df": services.load_jobs()}
    filters = {"search": "", "platforms": [], "max_age": 0}

    def threshold() -> int:
        return config.llm.score_threshold

    def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
        """Filtres de la barre d'outils (texte, plateformes, ancienneté)."""
        if filters["search"]:
            text = (df[Col.TITLE].fillna("") + " " + df[Col.COMPANY].fillna("")).str.lower()
            df = df[text.str.contains(filters["search"].lower(), regex=False)]
        if filters["platforms"]:
            df = df[df[Col.PLATFORM].isin(filters["platforms"])]
        if filters["max_age"]:
            df = df[df[Col.DAYS_OLD].fillna(0) <= filters["max_age"]]
        return df

    def on_change() -> None:
        """Après une action ou un changement de filtre : tout recharger."""
        state["df"] = services.load_jobs()
        for browser in browsers.values():
            browser.reload()
        nav.refresh()

    def set_status(status: Status):
        return lambda job: services.store.set_status([job[Col.ID]], status)

    def rehabilitate(job: dict) -> None:
        services.store.set_forced_relevant([job[Col.ID]], True)
        ui.notify("Offre remise dans les offres à traiter", type="positive")

    def set_filter(name: str, value) -> None:
        filters[name] = value
        on_change()

    # ------------------------------------------------------------ barre d'outils
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-end gap-4"):
            ui.input("Rechercher (titre, entreprise)", on_change=lambda e: set_filter("search", e.value or "")) \
                .props("clearable dense debounce=300 prepend-icon=search").classes("w-72")
            ui.select(PLATFORM_LABELS, label="Plateformes", multiple=True,
                      on_change=lambda e: set_filter("platforms", e.value or [])) \
                .props("dense use-chips clearable").classes("w-72")
            ui.select(AGE_OPTIONS, value=0, label="Ancienneté",
                      on_change=lambda e: set_filter("max_age", e.value)).props("dense").classes("w-48")
            ui.space()
            with ui.column().classes("gap-0 w-72"):
                threshold_label = ui.label(f"Seuil de pertinence IA : {threshold()}").classes("text-caption")
                slider = ui.slider(min=0, max=100, step=5, value=threshold()).props("label")

        def save_threshold() -> None:
            config.llm.score_threshold = int(slider.value)
            save_config(config)
            threshold_label.text = f"Seuil de pertinence IA : {threshold()}"
            on_change()

        slider.on("change", save_threshold)  # à la fin du glissement seulement

    # ------------------------------------------------------------------ onglets
    with ui.tabs(value="todo").classes("w-full") as tabs:
        tab_todo = ui.tab("todo", "À traiter", icon="inbox")
        tab_rejected = ui.tab("rejected", "Écartées", icon="filter_alt_off")
        tab_read = ui.tab("read", "Déjà lues", icon="drafts")

    browsers: dict[str, JobBrowser] = {}
    with ui.tab_panels(tabs, value="todo").classes("w-full bg-transparent") as panels:
        with ui.tab_panel(tab_todo).classes("p-0"):
            with ui.row().classes("w-full justify-end"):
                ui.button("Tout marquer comme lu", icon="done_all", on_click=lambda: confirm_mark_all()) \
                    .props("flat color=grey-8")
            browsers["todo"] = JobBrowser(
                get_rows=lambda: apply_filters(services.view_todo(state["df"], threshold())),
                actions=lambda job: [
                    Action("Lue", "done", set_status(Status.LUE), "grey-8", "l"),
                    Action("Postuler", "send", set_status(Status.POSTULEE), "primary", "p"),
                ],
                on_change=on_change, threshold=threshold,
                empty_text="Aucune offre à traiter. Lancez un scraping ou baissez le seuil.",
            )
        with ui.tab_panel(tab_rejected).classes("p-0"):
            browsers["rejected"] = JobBrowser(
                get_rows=lambda: apply_filters(services.view_rejected(state["df"], threshold())),
                actions=lambda job: [
                    Action("Réhabiliter", "restore", rehabilitate, "primary", "r"),
                    Action("Lue", "done", set_status(Status.LUE), "grey-8", "l"),
                ],
                on_change=on_change, threshold=threshold,
                empty_text="Aucune offre écartée.",
            )
        with ui.tab_panel(tab_read).classes("p-0"):
            browsers["read"] = JobBrowser(
                get_rows=lambda: apply_filters(services.view_status(state["df"], Status.LUE)),
                actions=lambda job: [
                    Action("Remettre à traiter", "undo", set_status(Status.NOUVELLE), "grey-8", "r"),
                    Action("Postuler", "send", set_status(Status.POSTULEE), "primary", "p"),
                ],
                on_change=on_change, threshold=threshold,
                empty_text="Aucune offre lue.",
            )

    # ---------------------------------------------------------- tout marquer lu
    async def confirm_mark_all() -> None:
        rows = browsers["todo"].rows
        if rows.empty:
            return
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Marquer les {len(rows)} offres affichées comme lues ?")
            with ui.row().classes("w-full justify-end"):
                ui.button("Annuler", on_click=lambda: dialog.submit(False)).props("flat")
                ui.button("Confirmer", on_click=lambda: dialog.submit(True))
        if await dialog:
            services.store.set_status(rows[Col.ID].tolist(), Status.LUE)
            ui.notify(f"{len(rows)} offre(s) marquée(s) comme lue(s)")
            on_change()

    # ----------------------------------------------------------------- clavier
    def on_key(e) -> None:
        if e.action.keydown:
            browsers[panels.value].handle_key(e.key.name)  # onglet affiché

    ui.keyboard(on_key=on_key)
