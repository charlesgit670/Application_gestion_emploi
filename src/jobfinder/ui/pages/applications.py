"""Page « Candidatures » : suivi des offres postulées, des entretiens et des refus (règle R7).

Pour chaque candidature : date de candidature, notes libres (enregistrées en quittant
le champ) et rappel de relance après `follow_up_days` jours sans nouvelle.
Le nombre d'entretiens réalisés est conservé même après un refus : il alimente les
statistiques (taux d'entretien) du tableau de bord.
Raccourcis : ← / →, E = entretien réalisé, X = refusée, R = relancée / réactiver.
"""
from datetime import date

import pandas as pd
from nicegui import ui

from jobfinder.config import load_config
from jobfinder.models import Col, Status
from jobfinder.ui import services
from jobfinder.ui.job_browser import Action, JobBrowser
from jobfinder.ui.layout import page_frame


@ui.page("/candidatures")
def applications_page() -> None:
    nav = page_frame("Candidatures", "/candidatures")
    config = load_config()
    state = {"df": services.load_jobs()}

    def on_change() -> None:
        state["df"] = services.load_jobs()
        for browser in browsers.values():
            browser.reload()
        nav.refresh()

    def set_status(status: Status, message: str):
        def handler(job: dict) -> None:
            services.store.set_status([job[Col.ID]], status)
            ui.notify(message)
        return handler

    def follow_up(job: dict) -> None:
        services.store.log_follow_up(job[Col.ID])
        ui.notify("Relance notée", type="positive")

    def add_interview(job: dict) -> None:
        count = services.store.add_interview(job[Col.ID])
        ui.notify(f"Entretien n°{count} enregistré. Bonne chance !", type="positive")

    def remove_interview(job: dict) -> None:
        count = services.store.remove_interview(job[Col.ID])
        ui.notify(f"Dernier entretien annulé ({count} restant(s))")

    def application_details(job: dict) -> None:
        """Bloc affiché sous les boutons : dates, rappel de relance, notes."""
        applied_on = job.get(Col.APPLIED_ON)
        waiting = services.days_without_news(pd.DataFrame([job])).iloc[0]
        with ui.row().classes("items-center gap-4 q-mt-sm text-grey-8"):
            if pd.notna(applied_on):
                ui.label(f"Candidature envoyée le {applied_on:%d/%m/%Y} "
                         f"({(date.today() - applied_on.date()).days} j)")
            if pd.notna(waiting):
                ui.label(f"Dernière activité il y a {int(waiting)} j")
            interviews = int(job.get(Col.INTERVIEW_COUNT) or 0)
            if interviews:
                ui.badge(f"{interviews} entretien(s) réalisé(s)").props("color=positive")

        if job[Col.STATUS] == Status.POSTULEE and pd.notna(waiting) and waiting >= config.follow_up_days:
            with ui.row().classes("w-full items-center tint-warning rounded-borders q-pa-sm"):
                ui.icon("notifications_active", color="orange-9")
                ui.label(f"Pas de nouvelle depuis {int(waiting)} jours : pensez à relancer.")

        notes = ui.textarea("Notes (contacts, échanges, dates d'entretien…)", value=job.get(Col.NOTES) or "") \
            .props("outlined autogrow").classes("w-full q-mt-sm")
        notes.on("blur", lambda: services.store.set_notes(job[Col.ID], notes.value))

    def common(**kwargs) -> dict:
        return dict(on_change=on_change, threshold=lambda: config.llm.score_threshold,
                    detail_extra=application_details, **kwargs)

    with ui.tabs(value="applied").classes("w-full") as tabs:
        ui.tab("applied", "Postulées", icon="send")
        ui.tab("interview", "Entretiens", icon="record_voice_over")
        ui.tab("refused", "Refusées", icon="block")

    browsers: dict[str, JobBrowser] = {}
    with ui.tab_panels(tabs, value="applied").classes("w-full bg-transparent") as panels:
        with ui.tab_panel("applied").classes("p-0"):
            browsers["applied"] = JobBrowser(
                get_rows=lambda: services.view_status(state["df"], Status.POSTULEE),
                actions=lambda job: [
                    Action("Entretien réalisé", "record_voice_over", add_interview, "positive", "e"),
                    Action("Refusée", "block", set_status(Status.REFUSEE, "Candidature archivée"), "negative", "x"),
                    Action("Relancée", "notifications", follow_up, "orange-8", "r"),
                    Action("Annuler", "undo", set_status(Status.NOUVELLE, "Remise dans les offres à traiter"), "grey-8"),
                ],
                empty_text="Aucune candidature en attente. C'est le moment d'envoyer des CV !",
                **common(),
            )
        with ui.tab_panel("interview").classes("p-0"):
            browsers["interview"] = JobBrowser(
                get_rows=lambda: services.view_status(state["df"], Status.ENTRETIEN),
                actions=lambda job: [
                    Action("Nouvel entretien", "add", add_interview, "positive", "e"),
                    Action("Refusée", "block", set_status(Status.REFUSEE, "Candidature archivée"), "negative", "x"),
                    Action("Annuler le dernier entretien", "undo", remove_interview, "grey-8"),
                ],
                empty_text="Aucun entretien en cours.",
                **common(),
            )
        with ui.tab_panel("refused").classes("p-0"):
            browsers["refused"] = JobBrowser(
                get_rows=lambda: services.view_status(state["df"], Status.REFUSEE),
                actions=lambda job: [
                    Action("Réactiver", "restore", set_status(Status.POSTULEE, "Candidature réactivée"), "primary", "r"),
                ],
                empty_text="Aucun refus pour le moment.",
                **common(),
            )

    ui.keyboard(on_key=lambda e: browsers[panels.value].handle_key(e.key.name) if e.action.keydown else None)
