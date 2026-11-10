"""Test du pipeline complet avec de faux scrapers et un faux LLM (aucun réseau)."""
import asyncio

import pandas as pd

from conftest import make_jobs
from jobfinder.config import AppConfig, PreFilterConfig
from jobfinder.llm import LlmError, Verdict
from jobfinder.models import Col
from jobfinder.pipeline import PipelineProgress, run_pipeline

FR = "Nous recherchons un data scientist pour développer des modèles statistiques en Python."
EN = "We are looking for a data scientist to build statistical models in Python for our team."


def fake_scraper(df: pd.DataFrame, fail: bool = False):
    """Fabrique une classe qui se comporte comme un scraper et renvoie `df`."""
    class Fake:
        def __init__(self, config):
            pass

        def run(self, progress):
            if fail:
                raise ConnectionError("site en panne")
            progress(len(df), len(df))
            return df
    return Fake


class FakeScorer:
    """Faux LLM : 80 sauf pour les titres contenant « KO » (réponse illisible)."""
    async def score(self, title, company, content):
        if "KO" in title:
            raise LlmError("réponse illisible")
        return Verdict(80, "pertinente")


def _config(**overrides):
    base = dict(keywords=["data"], url={"hw": "u", "ft": "u"}, launch_scrap={"hw": True, "ft": True},
                use_llm=True, language_filter={"fr": True, "en": False, "autre": False},
                pre_filter=PreFilterConfig(enabled=True, blacklist=["stage"]))
    base.update(overrides)
    return AppConfig(**base)


def test_pipeline_complet(store):
    store.insert(make_jobs(1, platform="hw", content=FR))  # h0 est déjà en base

    hw = make_jobs(4, platform="hw", content=[FR, FR, EN, FR],
                   title=["déjà vue", "Data Scientist", "English job", "Stage data"])
    ft_jobs = make_jobs(1, platform="ft", content=[FR], title=["Data KO"])
    ft_jobs["hash"], ft_jobs["link"] = ["ft0"], ["https://ft/0"]

    progress = PipelineProgress()
    report = asyncio.run(run_pipeline(
        _config(), store, progress,
        scrapers={"hw": fake_scraper(hw), "ft": fake_scraper(ft_jobs)},
        scorer=FakeScorer(),
    ))

    assert report.new == 4              # h0 était déjà en base
    assert report.wrong_language == 1   # l'offre en anglais : enregistrée avec score 0
    assert report.pre_filtered == 1     # « Stage » : enregistrée avec score 0
    assert report.inserted == 4
    # « Data Scientist » + l'offre h0 déjà en base mais jamais évaluée (R6)
    assert report.scored == 2 and report.llm_failures == 1

    df = store.load().set_index(Col.TITLE)
    assert df.loc["Stage data", Col.SCORE] == 0
    assert df.loc["English job", Col.SCORE] == 0
    assert "langue" in df.loc["English job", Col.AI_COMMENT]
    assert df.loc["Data Scientist", Col.SCORE] == 80
    assert pd.isna(df.loc["Data KO", Col.SCORE])  # échec LLM : sera réessayée (R6)
    assert not progress.running


def test_une_plateforme_en_panne_n_empeche_pas_les_autres(store):
    report = asyncio.run(run_pipeline(
        _config(use_llm=False), store,
        scrapers={"hw": fake_scraper(make_jobs(2, platform="hw", content=FR)),
                  "ft": fake_scraper(pd.DataFrame(), fail=True)},
    ))
    assert report.inserted == 2
    assert "ft" in report.failed_platforms


def test_offres_non_evaluees_reessayees_au_scraping_suivant(store):
    store.insert(make_jobs(2, platform="hw", content=FR))  # jamais évaluées
    report = asyncio.run(run_pipeline(
        _config(), store, scrapers={"hw": fake_scraper(pd.DataFrame()), "ft": fake_scraper(pd.DataFrame())},
        scorer=FakeScorer(),
    ))
    assert report.scored == 2
    assert store.unscored_ids() == []
