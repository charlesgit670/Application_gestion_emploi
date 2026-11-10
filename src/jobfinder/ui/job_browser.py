"""Composant « liste + détail » utilisé par les pages Offres et Candidatures.

    ┌──────────────────────┬──────────────────────────────────────────┐
    │ ‹ 1 2 3 ›            │ Data Scientist                           │
    │ ▌Data Scientist  82  │ EDF · LinkedIn · il y a 2 j     82 / 100 │
    │  ML Engineer     64  │ [Lue (L)] [Postuler (P)] [Voir l'offre]  │
    │  ...                 │ Analyse de l'IA : ...                    │
    │                      │ Description : ...                        │
    └──────────────────────┴──────────────────────────────────────────┘

La page fournit :
    - get_rows()       : les offres à afficher (DataFrame déjà trié)
    - actions(job)     : les boutons proposés pour une offre
    - on_change()      : à appeler après une action (recharger les données, compteurs...)
Après une action, l'offre quitte en général la liste : la suivante s'affiche
automatiquement à la même position, ce qui permet de trier les offres à la chaîne.
"""
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from nicegui import ui

from jobfinder.models import PLATFORM_LABELS, STATUS_LABELS, Col, Status
from jobfinder.ui import services
from jobfinder.ui.layout import age_text, score_badge

PAGE_SIZE = 20


@dataclass
class Action:
    """Un bouton d'action sur une offre."""
    label: str
    icon: str
    handler: Callable[[dict], None]  # reçoit l'offre sous forme de dictionnaire
    color: str = "primary"
    shortcut: str | None = None      # touche clavier (ex : "l")


class JobBrowser:
    def __init__(self, get_rows: Callable[[], pd.DataFrame], actions: Callable[[dict], list[Action]],
                 on_change: Callable[[], None], threshold: Callable[[], int], empty_text: str,
                 detail_extra: Callable[[dict], None] | None = None):
        self.get_rows = get_rows
        self.actions = actions
        self.on_change = on_change
        self.threshold = threshold
        self.empty_text = empty_text
        self.detail_extra = detail_extra  # contenu supplémentaire sous les boutons (ex : notes)
        self.rows = get_rows()
        self.index = 0  # position de l'offre sélectionnée dans self.rows

        with ui.row().classes("w-full no-wrap items-start gap-4"):
            with ui.column().classes("w-[26rem] shrink-0 gap-2"):
                self._render_list()
            with ui.column().classes("grow min-w-0"):
                self._render_detail()

    # ------------------------------------------------------------- navigation
    @property
    def current(self) -> pd.Series | None:
        return None if self.rows.empty else self.rows.iloc[self.index]

    def reload(self) -> None:
        """Relit les offres (après une action ou un changement de filtre)."""
        self.rows = self.get_rows()
        self.index = min(self.index, max(len(self.rows) - 1, 0))
        self._render_list.refresh()
        self._render_detail.refresh()

    def select(self, index: int) -> None:
        if self.rows.empty:
            return
        self.index = max(0, min(index, len(self.rows) - 1))
        self._render_list.refresh()
        self._render_detail.refresh()

    def handle_key(self, key: str) -> None:
        """Raccourcis : ← / → pour naviguer, puis la touche propre à chaque action."""
        if key in ("ArrowRight", "j"):
            self.select(self.index + 1)
        elif key in ("ArrowLeft", "k"):
            self.select(self.index - 1)
        elif self.current is not None:
            job = self._current_job()
            for action in self.actions(job):
                if action.shortcut and key.lower() == action.shortcut:
                    self._run(action, job)
                    break

    def _current_job(self) -> dict:
        return services.store.get(int(self.current[Col.ID])) or {}

    def _run(self, action: Action, job: dict) -> None:
        action.handler(job)
        self.on_change()

    # ------------------------------------------------------------- affichage
    @ui.refreshable_method
    def _render_list(self) -> None:
        total = len(self.rows)
        if total == 0:
            ui.label(self.empty_text).classes("text-grey-7 p-4")
            return

        pages = (total - 1) // PAGE_SIZE + 1
        page = self.index // PAGE_SIZE + 1
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"{total} offre(s)").classes("text-grey-7")
            if pages > 1:
                ui.pagination(1, pages, direction_links=True, value=page,
                              on_change=lambda e: self.select((e.value - 1) * PAGE_SIZE)).props("max-pages=5 size=sm")

        start = (page - 1) * PAGE_SIZE
        threshold = self.threshold()
        with ui.list().props("bordered separator").classes("w-full rounded-borders"):
            for position, row in enumerate(self.rows.iloc[start:start + PAGE_SIZE].itertuples(), start=start):
                item = ui.item(on_click=lambda p=position: self.select(p)).classes("job-item")
                if position == self.index:
                    item.classes("selected")
                with item:
                    with ui.item_section():
                        ui.item_label(row.title).classes("font-medium ellipsis")
                        platform = PLATFORM_LABELS.get(row.platform, row.platform)
                        ui.item_label(f"{row.company} · {platform} · {age_text(row.days_old)}") \
                            .props("caption").classes("ellipsis")
                    with ui.item_section().props("side"):
                        score_badge(row.score, threshold)

    @ui.refreshable_method
    def _render_detail(self) -> None:
        if self.current is None:
            return
        job = self._current_job()
        threshold = self.threshold()

        with ui.card().classes("w-full"):
            ui.label(job[Col.TITLE]).classes("text-h5 font-medium")
            with ui.row().classes("items-center gap-2 text-grey-8"):
                ui.icon("business")
                ui.label(job[Col.COMPANY]).classes("text-subtitle1")
                ui.badge(PLATFORM_LABELS.get(job[Col.PLATFORM], job[Col.PLATFORM])).props("outline color=primary")
                ui.label(age_text(job[Col.DAYS_OLD]))
                score_badge(job[Col.SCORE], threshold)
                if job[Col.STATUS] != Status.NOUVELLE:
                    ui.badge(STATUS_LABELS[Status(job[Col.STATUS])]).props("color=grey-7")

            with ui.row().classes("gap-2 mt-2"):
                for action in self.actions(job):
                    hint = f" ({action.shortcut.upper()})" if action.shortcut else ""
                    ui.button(action.label + hint, icon=action.icon,
                              on_click=lambda a=action: self._run(a, job)).props(f"color={action.color} unelevated")
                ui.button("Voir l'offre", icon="open_in_new",
                          on_click=lambda: ui.navigate.to(job[Col.LINK], new_tab=True)).props("flat")

            if isinstance(job.get(Col.AI_COMMENT), str) and job[Col.AI_COMMENT].strip():
                with ui.card().props("flat bordered").classes("w-full tint-primary q-mt-sm"):
                    ui.label("Analyse de l'IA").classes("text-caption text-primary font-medium")
                    ui.label(job[Col.AI_COMMENT])

            if self.detail_extra:
                self.detail_extra(job)

        with ui.card().classes("w-full"):
            ui.label("Description").classes("text-subtitle2 text-grey-7")
            ui.label(job.get(Col.CONTENT) or "Description non disponible.").classes("job-description")
