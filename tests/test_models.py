"""Tests des règles de pertinence (R2 : seuil appliqué à l'affichage)."""
import pandas as pd

from jobfinder.models import Col, Status, new_relevant_offers, offers_rejected_by_ai


def _df():
    return pd.DataFrame({
        Col.STATUS: [Status.NOUVELLE] * 4 + [Status.LUE],
        Col.SCORE: pd.array([80, 40, None, 10, 10], dtype="Int64"),
        Col.FORCED_RELEVANT: [0, 0, 0, 1, 0],
    })


def test_repartition_avec_seuil_50():
    df = _df()
    # 80 -> pertinente ; None -> non évaluée donc affichée ; 10 forcée -> affichée
    assert list(new_relevant_offers(df, 50).index) == [0, 2, 3]
    assert list(offers_rejected_by_ai(df, 50).index) == [1]


def test_baisser_le_seuil_ramene_des_offres():
    df = _df()
    assert 1 in new_relevant_offers(df, 30).index
    assert offers_rejected_by_ai(df, 30).empty


def test_une_offre_lue_n_apparait_nulle_part():
    df = _df()
    assert 4 not in new_relevant_offers(df, 0).index
    assert 4 not in offers_rejected_by_ai(df, 100).index
