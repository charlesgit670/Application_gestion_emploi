"""Tests de la base SQLite : insertion, dédoublonnage et changements de statut."""
from datetime import date

import pandas as pd

from conftest import make_jobs
from jobfinder.models import Col, Status


def test_insert_ignore_les_doublons(store):
    assert store.insert(make_jobs(3)) == 3
    # Réinsérer les mêmes offres n'ajoute rien
    assert store.insert(make_jobs(3)) == 0
    assert store.count() == 3


def test_doublon_par_lien_meme_si_hash_different(store):
    store.insert(make_jobs(1))
    autre = make_jobs(1, hash=["autre_hash"])  # même lien, contenu modifié
    assert store.insert(autre) == 0


def test_valeurs_par_defaut(store):
    store.insert(make_jobs(1))
    job = store.load().iloc[0]
    assert job[Col.STATUS] == Status.NOUVELLE
    assert pd.isna(job[Col.SCORE])
    assert job[Col.FORCED_RELEVANT] == 0


def test_date_de_publication_inconnue(store):
    store.insert(make_jobs(1, published_on=[None]))
    job = store.load().iloc[0]
    assert pd.isna(job[Col.PUBLISHED_ON])
    assert pd.isna(job[Col.DAYS_OLD])


def test_postuler_renseigne_la_date_de_candidature(store):
    store.insert(make_jobs(1))
    job_id = int(store.load()[Col.ID].iloc[0])

    store.set_status([job_id], Status.POSTULEE)
    job = store.load().iloc[0]
    assert job[Col.STATUS] == Status.POSTULEE
    assert job[Col.APPLIED_ON].date() == date.today()

    # Passer en entretien conserve la date de candidature
    store.set_status([job_id], Status.ENTRETIEN)
    assert store.load().iloc[0][Col.APPLIED_ON].date() == date.today()

    # Annuler la candidature (retour à NOUVELLE) efface la date
    store.set_status([job_id], Status.NOUVELLE)
    assert pd.isna(store.load().iloc[0][Col.APPLIED_ON])


def test_unscored_ids(store):
    store.insert(make_jobs(3, score=[None, 80, None]))
    ids = store.load().set_index(Col.HASH)[Col.ID]
    assert sorted(store.unscored_ids()) == sorted([ids["h0"], ids["h2"]])

    store.set_ai_result(int(ids["h0"]), 30, "trop data engineer")
    assert store.unscored_ids() == [ids["h2"]]


def test_notes(store):
    store.insert(make_jobs(1))
    job_id = int(store.load()[Col.ID].iloc[0])
    store.set_notes(job_id, "Relancé par mail")
    assert store.load().iloc[0][Col.NOTES] == "Relancé par mail"


def test_chargement_leger_et_lecture_d_une_offre(store):
    store.insert(make_jobs(2))
    light = store.load(with_content=False)
    assert Col.CONTENT not in light.columns and len(light) == 2
    job = store.get(int(light[Col.ID].iloc[0]))
    assert job[Col.CONTENT] == "Description"
    assert store.get(999) is None
