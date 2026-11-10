"""Chemins du projet.

Tous les chemins sont absolus et calculés à partir de l'emplacement de ce fichier :
l'application fonctionne donc quel que soit le dossier depuis lequel on la lance.

La variable d'environnement JOBFINDER_DATA_DIR permet d'utiliser un autre dossier de
données (ex : tester l'application sur une copie sans toucher aux vraies données).
"""
import os
from pathlib import Path

# src/jobfinder/paths.py -> remonter de 3 niveaux pour obtenir la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("JOBFINDER_DATA_DIR", PROJECT_ROOT / "data"))
BACKUP_DIR = DATA_DIR / "backup"

DB_PATH = DATA_DIR / "jobs.db"
LEGACY_CSV_PATH = DATA_DIR / "job.csv"  # ancien format de stockage (avant SQLite)
LOG_PATH = DATA_DIR / "jobfinder.log"

CONFIG_PATH = PROJECT_ROOT / "config.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config_default.json"
ENV_PATH = PROJECT_ROOT / ".env"
