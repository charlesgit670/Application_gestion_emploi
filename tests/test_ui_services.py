"""Tests des règles utilisées par l'interface (listes, compteurs, relances)."""
from datetime import date, timedelta

from conftest import make_jobs
from jobfinder.config import AppConfig
from jobfinder.models import Col, Status
from jobfinder.ui import services


def test_compteurs_et_vues(store):
    store.insert(make_jobs(4, score=[80, 20, None, 90]))
    ids = store.load().set_index(Col.HASH)[Col.ID]
    store.set_status([ids["h3"]], Status.POSTULEE)
    df = store.load(with_content=False)

    numbers = services.counts(df, AppConfig())
    assert numbers["todo"] == 2       # score 80 + non évaluée
    assert numbers["rejected"] == 1   # score 20
    assert numbers["active"] == 1
    assert list(services.view_rejected(df, 50)[Col.HASH]) == ["h1"]


def test_relance_apres_n_jours(store):
    store.insert(make_jobs(3))
    ids = store.load()[Col.ID].tolist()
    store.set_status(ids, Status.POSTULEE)

    old = (date.today() - timedelta(days=15)).isoformat()
    with store._connect() as conn:  # simule des candidatures envoyées il y a 15 jours
        conn.execute("UPDATE jobs SET applied_on = ?, status_changed_at = ? WHERE id IN (?, ?)",
                     (old, old + " 10:00:00", ids[0], ids[1]))
        conn.execute("UPDATE jobs SET applied_on = NULL, status_changed_at = NULL WHERE id = ?", (ids[2],))

    late = services.needs_follow_up(store.load(), follow_up_days=10)
    assert sorted(late[Col.ID]) == sorted(ids[:2])  # la candidature sans date est ignorée
    assert set(late["days_waiting"]) == {15}

    store.log_follow_up(ids[0])  # une relance remet le compteur à zéro
    late = services.needs_follow_up(store.load(), follow_up_days=10)
    assert list(late[Col.ID]) == [ids[1]]
    assert "Relance le" in store.get(ids[0])[Col.NOTES]


def test_statistiques_de_candidature(store):
    store.insert(make_jobs(5))
    ids = store.load()[Col.ID].tolist()
    store.set_status(ids[:4], Status.POSTULEE)   # 4 candidatures
    store.add_interview(ids[0])
    store.add_interview(ids[0])                  # 2 entretiens pour la 1re
    store.add_interview(ids[1])
    store.set_status([ids[1], ids[2]], Status.REFUSEE)

    stats = services.application_stats(store.load())
    assert stats["sent"] == 4
    assert stats["with_interview"] == 2
    assert stats["interview_rate"] == 0.5
    assert stats["interviews"] == 3
    assert stats["refused"] == 2 and stats["refused_after_interview"] == 1
    assert stats["waiting"] == 1


def test_pertinence_par_plateforme(store):
    store.insert(make_jobs(4, platform="hw", score=[80, 20, 30, None]))
    table = services.relevance_by_platform(store.load(), threshold=50)
    assert table.loc["hw", "evaluated"] == 3      # la non évaluée est exclue
    assert round(table.loc["hw", "percent"]) == 33
