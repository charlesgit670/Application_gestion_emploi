"""Déboguer un scraper depuis l'IDE (PyCharm, VS Code) : modifier les réglages ci-dessous,
placer des points d'arrêt dans src/jobfinder/scrapers/<site>.py, puis lancer ce fichier en mode Debug.

Rien n'est écrit dans la base. Les pages téléchargées et le résultat sont enregistrés dans
data/debug/<plateforme>_<date-heure>/ (voir src/jobfinder/scrapers/__main__.py).
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobfinder.logs import setup_logging  # noqa: E402
from jobfinder.scrapers.__main__ import debug_scraper  # noqa: E402

# ----------------------------------------------------------------- réglages
PLATFORM = "ft"          # linkedin | apec | hw | ft | sp
KEYWORDS = None          # ex : ["data scientist"] ; None = mots-clés de config.json
DAYS = None              # ex : 3 ; None = ancienneté de config.json
MAX_DETAILS = 3          # nombre de fiches détaillées lues ; None = toutes
SAVE_HTML = True         # sauvegarder chaque page téléchargée
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    setup_logging(logging.DEBUG)
    df = debug_scraper(PLATFORM, KEYWORDS, DAYS, MAX_DETAILS, SAVE_HTML)
