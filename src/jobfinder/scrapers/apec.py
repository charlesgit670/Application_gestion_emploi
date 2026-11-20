"""Scraper APEC : lance apec_worker.py dans un processus séparé et lit ses messages.

Voir apec_worker.py pour l'explication du processus séparé et du protocole.
"""
import json
import logging
import os
import subprocess
import sys
from datetime import date

from jobfinder.config import AppConfig
from jobfinder.paths import PROJECT_ROOT
from jobfinder.scrapers.base import BaseScraper, ProgressCallback, RawJob

logger = logging.getLogger(__name__)

SRC_DIR = PROJECT_ROOT / "src"


class Apec(BaseScraper):
    key = "apec"
    label = "APEC"
    keyword_mode = "or"  # mode utilisé par apec_worker.py

    def __init__(self, config: AppConfig):
        super().__init__(config)
        self.config = config

    def scrape(self, progress: ProgressCallback) -> list[RawJob]:
        process = subprocess.Popen(
            [sys.executable, "-m", "jobfinder.scrapers.apec_worker"],
            cwd=SRC_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # les logs du processus enfant s'affichent dans la console
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        process.stdin.write(self.config.model_dump_json())
        process.stdin.close()

        raw_jobs = []
        for line in process.stdout:  # lecture au fil de l'eau -> progression en direct
            message = _parse_message(line)
            if "progress" in message:
                progress(*message["progress"])
            elif "jobs" in message:
                raw_jobs = message["jobs"]

        if process.wait() != 0:
            raise RuntimeError(f"Le processus APEC s'est arrêté avec le code {process.returncode}")

        return [
            RawJob(
                title=job["title"],
                company=job["company"],
                link=job["link"],
                content=job["content"],
                published_on=date.fromisoformat(job["published_on"]) if job["published_on"] else None,
                source_id=job["source_id"],
            )
            for job in raw_jobs
        ]


def _parse_message(line: str) -> dict:
    """Une ligne JSON du processus enfant ; toute autre sortie est ignorée."""
    line = line.strip()
    if not line.startswith("{"):
        return {}
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {}
