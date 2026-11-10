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
