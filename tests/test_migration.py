"""Tests de la conversion de l'ancien CSV (4 booléens) vers le statut unique."""
import pandas as pd

from jobfinder.migration import convert_legacy_dataframe, migrate_legacy_csv
from jobfinder.models import Col, Status


def _legacy():
    #            nouvelle  écartée  lue   postulée refusée  réhabilitée  non évaluée
    return pd.DataFrame({
        "title": ["t"] * 7, "content": ["c"] * 7, "company": ["co"] * 7,
        "link": [f"l{i}" for i in range(7)], "hash": [f"h{i}" for i in range(7)],
        "platform": ["hw"] * 7, "date": ["2026-10-01"] * 7, "comment": ["x"] * 7,
        "custom_profile": [None] * 7, "days_diff": [1] * 7,
        "is_read":       [0, 0, 1, 1, 1, 0, 0],
        "is_apply":      [0, 0, 0, 1, 1, 0, 0],
        "is_refused":    [0, 0, 0, 0, 1, 0, 0],
        "is_good_offer": [1, 0, 1, 1, 1, 1, 1],
        "score":         [80, 20, 60, 70, 90, 30, -1],
    })


def test_conversion_des_statuts():
    new = convert_legacy_dataframe(_legacy())
    assert list(new[Col.STATUS]) == [
        Status.NOUVELLE, Status.NOUVELLE, Status.LUE, Status.POSTULEE,
        Status.REFUSEE, Status.NOUVELLE, Status.NOUVELLE,
    ]
    assert list(new[Col.FORCED_RELEVANT]) == [0, 0, 0, 0, 0, 1, 0]
    assert pd.isna(new[Col.SCORE].iloc[6])  # -1 -> non évaluée


def test_migration_puis_aucune_reimportation(store, tmp_path):
    csv = tmp_path / "job.csv"
    _legacy().to_csv(csv, sep=";", index=False)
    assert migrate_legacy_csv(store, csv) == 7
    assert migrate_legacy_csv(store, csv) == 0  # base non vide : rien à faire
