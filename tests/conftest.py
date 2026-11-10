"""Configuration commune des tests : rend le dossier src/ importable."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobfinder.storage import JobStore  # noqa: E402


@pytest.fixture
def store(tmp_path) -> JobStore:
    """Base SQLite vide, créée dans un dossier temporaire propre à chaque test."""
    return JobStore(tmp_path / "test.db")


def make_jobs(n: int, platform: str = "linkedin", **extra) -> pd.DataFrame:
    """Fabrique n offres factices (hash et lien uniques)."""
    data = {
        "hash": [f"h{i}" for i in range(n)],
        "link": [f"https://ex.com/{i}" for i in range(n)],
        "platform": platform,
        "title": [f"Data Scientist {i}" for i in range(n)],
        "company": "ACME",
        "content": "Description",
        "published_on": "2026-11-01",
    }
    data.update(extra)
    return pd.DataFrame(data)
