"""Lance JobFinder :  python run.py

L'application s'ouvre dans un onglet du navigateur (http://localhost:8080).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Sortie console en UTF-8 (accents corrects sur toutes les configurations Windows)
os.environ["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
# Préférences de l'interface (mode sombre...) rangées avec les données, hors du dépôt git
os.environ.setdefault("NICEGUI_STORAGE_PATH", str(ROOT / "data" / ".nicegui"))

from jobfinder.ui.main import main  # noqa: E402  (après la configuration du chemin)

if __name__ in {"__main__", "__mp_main__"}:
    main()
