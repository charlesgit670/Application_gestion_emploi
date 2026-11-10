"""Stockage des offres dans une base SQLite (data/jobs.db).

Pourquoi SQLite plutôt que le CSV ?
    Avec le CSV, chaque action réécrivait TOUT le fichier. Le scraping, qui dure
    plusieurs minutes, relisait le fichier au début et le réécrivait à la fin :
    les offres marquées "lue" / "postulée" entre-temps étaient écrasées.
    Avec SQLite, chaque action ne modifie que les lignes concernées, et le
    scraping se contente d'AJOUTER des lignes : plus de perte possible.

SQLite est inclus dans Python (module sqlite3) : rien à installer.
La base reste lisible depuis pandas :  pd.read_sql("SELECT * FROM jobs", conn)

Exemple :
    store = JobStore()
    df = store.load()
    store.set_status([12, 15], Status.LUE)
"""
import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from jobfinder.models import Col, Status
from jobfinder.paths import BACKUP_DIR, DB_PATH

logger = logging.getLogger(__name__)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS jobs (
    {Col.ID}                INTEGER PRIMARY KEY AUTOINCREMENT,
    {Col.HASH}              TEXT NOT NULL UNIQUE,
    {Col.LINK}              TEXT NOT NULL UNIQUE,
    {Col.PLATFORM}          TEXT NOT NULL,
    {Col.TITLE}             TEXT,
    {Col.COMPANY}           TEXT,
    {Col.CONTENT}           TEXT,
    {Col.PUBLISHED_ON}      TEXT,               -- 'AAAA-MM-JJ' ou NULL si inconnue
    {Col.SCRAPED_AT}        TEXT NOT NULL,      -- 'AAAA-MM-JJ HH:MM:SS'
    {Col.SCORE}             INTEGER,            -- NULL = pas encore évaluée
    {Col.AI_COMMENT}        TEXT,
    {Col.FORCED_RELEVANT}   INTEGER NOT NULL DEFAULT 0,
    {Col.STATUS}            TEXT NOT NULL DEFAULT '{Status.NOUVELLE}',
    {Col.STATUS_CHANGED_AT} TEXT,
    {Col.APPLIED_ON}        TEXT,
    {Col.NOTES}             TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs({Col.STATUS});
"""

# Colonnes qu'on peut fournir lors d'une insertion (id et scraped_at sont automatiques).
# Seules celles présentes dans le DataFrame sont utilisées ; les autres prennent
# leur valeur par défaut (ex : status = 'nouvelle').
INSERTABLE_COLUMNS = [
    Col.HASH, Col.LINK, Col.PLATFORM, Col.TITLE, Col.COMPANY, Col.CONTENT,
    Col.PUBLISHED_ON, Col.SCORE, Col.AI_COMMENT,
    Col.FORCED_RELEVANT, Col.STATUS, Col.STATUS_CHANGED_AT, Col.APPLIED_ON, Col.NOTES,
]
REQUIRED_COLUMNS = [Col.HASH, Col.LINK, Col.PLATFORM]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_db_value(value):
    """Convertit une valeur pandas/numpy en valeur acceptée par sqlite3 (NaN -> NULL)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):  # types numpy (np.int64, np.float64...)
        return value.item()
    return value


class JobStore:
    """Accès à la table `jobs`. Une instance = un fichier de base."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        """Connexion courte : ouverte, utilisée, validée (commit) puis fermée."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            # WAL : l'interface peut lire pendant que le scraping écrit
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ lecture
    def load(self) -> pd.DataFrame:
        """Toutes les offres, avec la colonne calculée `days_old` (âge en jours)."""
        with self._connect() as conn:
            df = pd.read_sql("SELECT * FROM jobs", conn)

        df[Col.PUBLISHED_ON] = pd.to_datetime(df[Col.PUBLISHED_ON], errors="coerce")
        df[Col.APPLIED_ON] = pd.to_datetime(df[Col.APPLIED_ON], errors="coerce")
        df[Col.SCORE] = df[Col.SCORE].astype("Int64")  # entier acceptant les valeurs vides

        today = pd.Timestamp(date.today())
        df[Col.DAYS_OLD] = (today - df[Col.PUBLISHED_ON]).dt.days.astype("Int64")
        return df

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def known_keys(self) -> tuple[set[str], set[str]]:
        """(hashes, liens) déjà en base, pour détecter les nouvelles offres."""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT {Col.HASH}, {Col.LINK} FROM jobs").fetchall()
        return {r[0] for r in rows}, {r[1] for r in rows}

    def unscored_ids(self) -> list[int]:
        """Offres encore au statut NOUVELLE jamais évaluées par le LLM (règle R6)."""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {Col.ID} FROM jobs WHERE {Col.SCORE} IS NULL AND {Col.STATUS} = ?",
                (Status.NOUVELLE,),
            ).fetchall()
        return [r[0] for r in rows]

    # ---------------------------------------------------------------- écriture
    def insert(self, new_jobs: pd.DataFrame) -> int:
        """Ajoute des offres. Celles dont le hash ou le lien existe déjà sont ignorées.

        Retourne le nombre d'offres réellement ajoutées.
        """
        if new_jobs.empty:
            return 0
        missing = [c for c in REQUIRED_COLUMNS if c not in new_jobs.columns]
        if missing:
            raise ValueError(f"Colonnes obligatoires manquantes : {missing}")

        columns = [c for c in INSERTABLE_COLUMNS if c in new_jobs.columns]
        scraped_at = _now()
        rows = [
            [_to_db_value(v) for v in row] + [scraped_at]
            for row in new_jobs[columns].itertuples(index=False)
        ]
        columns.append(Col.SCRAPED_AT)

        sql = (f"INSERT OR IGNORE INTO jobs ({', '.join(columns)}) "
               f"VALUES ({', '.join('?' * len(columns))})")
        with self._connect() as conn:
            before = conn.total_changes
            conn.executemany(sql, rows)
            added = conn.total_changes - before

        logger.info("%d offre(s) ajoutée(s), %d ignorée(s) (déjà en base)", added, len(rows) - added)
        return added

    def set_status(self, job_ids: list[int], status: Status) -> None:
        """Change le statut d'une ou plusieurs offres.

        - Passage à POSTULEE : la date de candidature est remplie (si elle ne l'est pas déjà).
        - Retour à NOUVELLE ou LUE : la date de candidature est effacée.
        """
        status = Status(status)
        if status == Status.POSTULEE:
            applied_sql = f"COALESCE({Col.APPLIED_ON}, '{date.today():%Y-%m-%d}')"
        elif status in (Status.NOUVELLE, Status.LUE):
            applied_sql = "NULL"
        else:
            applied_sql = Col.APPLIED_ON  # inchangée

        with self._connect() as conn:
            conn.executemany(
                f"UPDATE jobs SET {Col.STATUS} = ?, {Col.STATUS_CHANGED_AT} = ?, "
                f"{Col.APPLIED_ON} = {applied_sql} WHERE {Col.ID} = ?",
                [(status.value, _now(), int(job_id)) for job_id in job_ids],
            )

    def set_forced_relevant(self, job_ids: list[int], forced: bool = True) -> None:
        """Réhabilite (ou non) des offres écartées par l'IA, quel que soit le seuil."""
        with self._connect() as conn:
            conn.executemany(
                f"UPDATE jobs SET {Col.FORCED_RELEVANT} = ? WHERE {Col.ID} = ?",
                [(int(forced), int(job_id)) for job_id in job_ids],
            )

    def set_notes(self, job_id: int, notes: str) -> None:
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {Col.NOTES} = ? WHERE {Col.ID} = ?", (notes, int(job_id)))

    def set_ai_result(self, job_id: int, score: int | None, comment: str) -> None:
        """Enregistre le résultat de l'évaluation LLM d'une offre."""
        with self._connect() as conn:
            conn.execute(
                f"UPDATE jobs SET {Col.SCORE} = ?, {Col.AI_COMMENT} = ? WHERE {Col.ID} = ?",
                (score, comment, int(job_id)),
            )

    # --------------------------------------------------------------- utilitaires
    def backup(self) -> Path | None:
        """Copie horodatée de la base dans data/backup/ (avant un scraping par exemple)."""
        if not self.db_path.exists():
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"jobs_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
        with self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")  # tout écrire dans le fichier principal
        shutil.copy(self.db_path, target)
        return target

    def export_csv(self, path: Path) -> None:
        """Export de toute la base en CSV (séparateur ';', lisible dans Excel)."""
        self.load().drop(columns=[Col.DAYS_OLD]).to_csv(path, sep=";", index=False, encoding="utf-8-sig")
