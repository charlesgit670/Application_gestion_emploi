"""Tests de la détection des doublons probables entre plateformes (R5)."""
import pandas as pd

from jobfinder.duplicates import find_probable_duplicates, normalize_company, normalize_title


def test_normalisation():
    assert normalize_company("\nENGIE\n - 92 - Courbevoie") == "engie"
    assert normalize_company("Servier France") == normalize_company("SERVIER")
    assert normalize_title("Data Engineer (H / F)") == normalize_title("Data Engineer H/F") == "data engineer"
    assert normalize_title("Ingénieur IA - CDI") == "ingenieur ia"


def _df(rows):
    return pd.DataFrame(rows, columns=["id", "platform", "title", "company", "published_on"])


def test_doublon_entre_plateformes():
    df = _df([
        (1, "linkedin", "Data Engineer (H / F)", "Servier France", "2026-11-01"),
        (2, "hw", "Data Engineer H/F", "Servier", "2026-11-03"),
        (3, "hw", "Data Engineer H/F", "Servier", "2026-11-03"),           # même plateforme que 2
        (4, "apec", "Manager Data Scientist", "Servier", "2026-11-02"),   # autre poste
        (5, "ft", "Data Engineer", "Servier", "2026-06-01"),              # trop ancien
    ])
    duplicates = find_probable_duplicates(df)
    assert sorted(duplicates[1]) == [2, 3]
    assert duplicates[2] == [1]
    assert 4 not in duplicates and 5 not in duplicates
