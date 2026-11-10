"""Tests des briques communes des scrapers : mots-clés, dates, mise en forme."""
import hashlib
from datetime import date, timedelta

import pytest

from jobfinder.config import AppConfig
from jobfinder.scrapers.base import BaseScraper, RawJob, compute_hash
from jobfinder.scrapers.dates import parse_french_date, parse_relative_date
from jobfinder.scrapers.keywords import build_keyword_terms, build_keyword_urls

TODAY = date(2026, 11, 10)


# ----------------------------------------------------------------- mots-clés
def test_modes_de_mots_cles():
    kw = ["data scientist", " Machine Learning ", "DATA SCIENTIST", ""]
    assert build_keyword_terms(kw, "one_by_one") == ["data scientist", "Machine Learning"]
    assert build_keyword_terms(kw, "or") == ["data scientist OR Machine Learning"]
    assert build_keyword_terms(kw, "or", quote_terms_for_or=True) == ['"data scientist" OR "Machine Learning"']
    assert build_keyword_terms(kw, "all") == ["data scientist Machine Learning"]


def test_encodage_des_urls():
    assert build_keyword_urls("https://x.fr/?k={keyword}", ["data scientist"]) == ["https://x.fr/?k=data+scientist"]
    assert build_keyword_urls("https://x.fr/mot-cles/{keyword}/", ["data scientist"], encode_mode="path") \
        == ["https://x.fr/mot-cles/data%20scientist/"]


def test_modele_sans_keyword_refuse():
    with pytest.raises(ValueError):
        build_keyword_urls("https://x.fr/", ["data"])


# ---------------------------------------------------------------------- dates
@pytest.mark.parametrize("text, expected", [
    ("Publié aujourd'hui", TODAY),
    ("il y a 3 heures", TODAY),
    ("Publié hier", TODAY - timedelta(days=1)),
    ("il y a 5 jours", TODAY - timedelta(days=5)),
    ("il y a 2 semaines", TODAY - timedelta(weeks=2)),
    ("il y a 1 mois", TODAY - timedelta(days=30)),
    ("plus de 30 jours", TODAY - timedelta(days=30)),
    ("texte incompréhensible", None),  # R4 : date inconnue, et non plus « aujourd'hui »
    ("", None),
])
def test_dates_relatives(text, expected):
    assert parse_relative_date(text, today=TODAY) == expected


def test_date_en_francais():
    assert parse_french_date("12 octobre 2026") == date(2026, 10, 12)
    assert parse_french_date("05/11/2026") == date(2026, 11, 5)
    assert parse_french_date("n'importe quoi") is None


# ------------------------------------------------------------ classe de base
class FakeScraper(BaseScraper):
    key = "hw"
    label = "Test"

    def scrape(self, progress):
        return [
            RawJob("DS", "ACME", "https://a", "desc", TODAY),
            RawJob("DS", "ACME", "https://a", "desc", TODAY),  # doublon
            RawJob("ML", "Foo", "https://b", "texte", None),
        ]


def test_run_produit_un_dataframe_propre():
    df = FakeScraper(AppConfig()).run()
    assert list(df["link"]) == ["https://a", "https://b"]
    assert set(df["platform"]) == {"hw"}
    assert df["hash"].iloc[0] == compute_hash("hw", "DS", "ACME", "desc")
    assert "source_id" not in df.columns


def test_hash_identique_a_l_ancienne_formule():
    assert compute_hash("ft", "T", "C", "D") == hashlib.sha256("ftTCD".encode()).hexdigest()


def test_filtre_d_anciennete():
    scraper = FakeScraper(AppConfig(filter_day_scrap=7))
    assert scraper.is_recent(date.today())
    assert not scraper.is_recent(date.today() - timedelta(days=8))
    assert scraper.is_recent(None)  # date inconnue : conservée


def test_une_offre_en_erreur_n_arrete_pas_les_autres():
    scraper = FakeScraper(AppConfig())
    jobs = [RawJob("a", "c", "l1"), RawJob("b", "c", "l2"), RawJob("c", "c", "l3")]
    seen = []

    def read(job):
        if job.link == "l2":
            raise ConnectionError("site muet")
        return "description"

    result = scraper.fetch_details(jobs, lambda i, n: seen.append((i, n)), read)
    assert [j.link for j in result] == ["l1", "l3"]
    assert seen == [(1, 3), (2, 3), (3, 3)]  # la progression avance quand même
