"""Tests de lecture des pages HTML, sur des extraits fictifs (aucun accès réseau)."""
from datetime import date

from bs4 import BeautifulSoup

from jobfinder.config import AppConfig
from jobfinder.scrapers.apec_worker import build_payload, html_to_text, parse_apec_date, parse_search_url
from jobfinder.scrapers.francetravail import FranceTravail
from jobfinder.scrapers.hellowork import HelloWork
from jobfinder.scrapers.linkedin import Linkedin
from jobfinder.scrapers.servicepublic import ServicePublic


def _item(html: str):
    return BeautifulSoup(html, "html.parser").find("li")


def test_carte_hellowork():
    # Structure du site depuis octobre 2026 : <span> dans le <h3>
    job = HelloWork._read_card(_item("""
        <li><a data-cy="offerTitle" href="/fr-fr/emplois/1.html"><h3 class="inline">
        <span class="block typo-l">Data Scientist</span> <span class="inline typo-s">EDF</span></h3></a>
        <div class="text-grey-500">il y a 2 jours</div></li>"""))
    assert (job.title, job.company) == ("Data Scientist", "EDF")
    assert job.link == "https://www.hellowork.com/fr-fr/emplois/1.html"
    assert job.published_on is not None


def test_carte_hellowork_incomplete():
    assert HelloWork._read_card(_item("<li><p>pub</p></li>")) is None


def test_carte_france_travail():
    job = FranceTravail._read_card(_item("""
        <li><a class="media with-fav" href="/offres/123"><div class="media-body">
        <h2> Data Scientist </h2><p class="subtext">ENGIE - 92</p><p class="date">Publié hier</p>
        </div></a></li>"""))
    assert (job.title, job.company) == ("Data Scientist", "ENGIE - 92")
    assert job.link == "https://candidat.francetravail.fr/offres/123"


def test_carte_service_public():
    job = ServicePublic._read_card(_item("""
        <li class="fr-col-12 item"><a class="is-same-domain" href="https://sp.fr/o/1">Data scientist</a>
        <img class="fr-responsive-img" alt="Ministère des Armées"/>
        <ul><li class="fr-icon-calendar-line">En ligne depuis le 12 octobre 2026</li></ul></li>"""))
    assert job.company == "Ministère des Armées"
    assert job.published_on == date(2026, 10, 12)


def test_urls_de_recherche():
    config = AppConfig(
        keywords=["data scientist", "ml"],
        url={
            "hw": "https://www.hellowork.com/fr-fr/emploi/recherche.html?k=Data+scientist&k_autocomplete=x&l=Nanterre",
            "ft": "https://candidat.francetravail.fr/offres/recherche?lieux=92050&motsCles=data&range=0-19&rayon=20",
            "sp": "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/mot-cles/data%20scientist/localisation/283/",
            "linkedin": "https://www.linkedin.com/jobs/search?keywords=Data&location=Nanterre",
        },
        keyword_mode={"hw": "one_by_one", "ft": "all", "sp": "one_by_one", "linkedin": "or"},
    )
    assert HelloWork(config).search_urls()[0] == \
        "https://www.hellowork.com/fr-fr/emploi/recherche.html?k=data+scientist&k_autocomplete=x&l=Nanterre"
    assert FranceTravail(config).search_urls() == \
        ["https://candidat.francetravail.fr/offres/recherche?lieux=92050&motsCles=data+scientist+ml&rayon=20"]
    assert ServicePublic(config).search_urls()[1] == \
        "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/mot-cles/ml/localisation/283/"
    assert Linkedin(config).search_urls() == \
        ["https://www.linkedin.com/jobs/search?keywords=%22data+scientist%22+OR+%22ml%22&location=Nanterre"]


# ------------------------------------------------------------------ APEC
def test_apec_parametres_et_payload():
    filters = parse_search_url("https://www.apec.fr/x?motsCles=DS&lieux=596212&typesContrat=101888&distance=15")
    assert filters == {"lieux": ["596212"], "typesConvention": [], "typesContrat": ["101888"], "distance": 15}

    payload = build_payload(filters, "DS", 20, geo={"latitude": 48.9, "longitude": 2.2})
    assert payload["pagination"] == {"range": 20, "startIndex": 20}
    assert payload["pointGeolocDeReference"]["distance"] == "15"
    assert "pointGeolocDeReference" not in build_payload(filters, "DS", 0, geo=None)


def test_apec_dates_et_html():
    assert parse_apec_date("2026-11-03T10:00:00") == date(2026, 11, 3)
    assert parse_apec_date("03/11/2026") == date(2026, 11, 3)
    assert parse_apec_date(None) is None
    assert html_to_text("<p>Bonjour&nbsp;<b>monde</b></p>\n\n") == "Bonjour monde"
