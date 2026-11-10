"""Démarrage de l'interface web (NiceGUI).

Au lancement :
    1. configuration du logging (console + data/jobfinder.log)
    2. migration unique de l'ancien data/job.csv vers la base SQLite (si besoin)
    3. enregistrement des pages, puis ouverture d'un onglet dans le navigateur
"""
import logging
import os

from nicegui import app, ui

from jobfinder.logs import setup_logging
from jobfinder.migration import migrate_legacy_csv
from jobfinder.ui import services
from jobfinder.ui.pages import applications, dashboard, offers, scraping  # noqa: F401  (enregistre les pages)

logger = logging.getLogger(__name__)

PORT = 8080


def main() -> None:
    setup_logging()
    imported = migrate_legacy_csv(services.store)
    if imported:
        logger.info("Première utilisation : %d offres importées depuis l'ancien fichier CSV", imported)

    app.on_startup(lambda: logger.info("JobFinder disponible sur http://localhost:%d", PORT))
    ui.run(
        title="JobFinder",
        port=PORT,
        language="fr",
        favicon="💼",
        reload=False,              # pas de rechargement automatique : application, pas développement
        show=not os.environ.get("JOBFINDER_NO_BROWSER"),  # ouvre un onglet du navigateur
        show_welcome_message=False,
    )
