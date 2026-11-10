"""Tests de la lecture des réponses LLM et des filtres avant LLM."""
import pytest

from jobfinder.config import PreFilterConfig
from jobfinder.filters import is_language_allowed, pre_filter_reason
from jobfinder.llm import LlmError, is_transient, parse_verdict


# ------------------------------------------------------------- réponses LLM
@pytest.mark.parametrize("text, score", [
    ('{"reponse": 75, "justification": "ML fort"}', 75),
    ('{"reponse": "60", "justification": "ok"}', 60),          # score en texte
    ('```json\n{"reponse": 30, "justification": "x"}\n```', 30),  # bloc markdown
    ('Voici : {"reponse": 150, "justification": "x"} fin', 100),  # borné à 100
    ('{"score": 42, "justification": "x"}', 42),
])
def test_parse_verdict(text, score):
    assert parse_verdict(text).score == score


@pytest.mark.parametrize("text", ["pas de json", '{"justification": "sans score"}', "{cassé"])
def test_reponses_illisibles(text):
    with pytest.raises(LlmError):
        parse_verdict(text)


class _HttpError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


def test_erreurs_temporaires():
    assert is_transient(_HttpError(429))
    assert is_transient(_HttpError(503))
    assert not is_transient(_HttpError(401))  # mauvaise clé : inutile de réessayer
    assert not is_transient(LlmError("JSON invalide"))


# -------------------------------------------------------------------- filtres
FR = "Nous recherchons un data scientist pour développer des modèles de prévision de la consommation."
EN = "We are looking for a data scientist to build forecasting models for energy consumption."


def test_filtre_de_langue():
    allowed = {"fr": True, "en": False, "autre": False}
    assert is_language_allowed(FR, allowed)
    assert not is_language_allowed(EN, allowed)
    assert is_language_allowed(EN, {"fr": True, "en": True, "autre": True})


def test_pre_filtre():
    config = PreFilterConfig(enabled=True, blacklist=["Stage"], whitelist=["python", "machine learning"])
    assert "Stage" in pre_filter_reason("Stage data", "python", config)
    assert "aucun mot requis" in pre_filter_reason("Data analyst", "Excel", config)
    assert pre_filter_reason("Data scientist", "Python et SQL", config) is None
    assert pre_filter_reason("Stage", "", PreFilterConfig(enabled=False, blacklist=["stage"])) is None
