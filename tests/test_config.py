"""Tests du chargement de la configuration."""
import json

import pytest
from pydantic import ValidationError

from jobfinder.config import AppConfig, load_config, save_config


def test_ancien_fichier_complete_par_les_valeurs_par_defaut(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"keywords": ["data"], "llm": {"provider": "Mistral"}}), encoding="utf-8")
    config = load_config(path)
    assert config.llm.provider == "Mistral"
    assert config.llm.score_threshold == 50  # nouveau champ, absent du fichier


def test_valeur_invalide_refusee():
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"keyword_mode": {"apec": "toto"}})


def test_aller_retour(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig(keywords=["ml"])
    config.llm.score_threshold = 65
    save_config(config, path)
    assert load_config(path).llm.score_threshold == 65


def test_erreurs_de_scraping():
    config = AppConfig(launch_scrap={"apec": True})
    errors = config.scraping_errors()
    assert any("mot-clé" in e for e in errors)
    assert any("apec" in e for e in errors)


def test_le_config_default_du_projet_est_valide():
    from jobfinder.paths import DEFAULT_CONFIG_PATH
    load_config(DEFAULT_CONFIG_PATH)


def test_cle_api_enregistree_dans_env(tmp_path, monkeypatch):
    from jobfinder.config import get_api_key, set_api_key
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    env = tmp_path / ".env"
    set_api_key("Mistral", "abc123", env)
    assert "MISTRAL_API_KEY='abc123'" in env.read_text()
    assert get_api_key("Mistral") == "abc123"
    assert get_api_key("Local") == ""


def test_ancien_prompt_converti_en_criteres():
    old_prompt = (
        "Ce que je veux :\n- Data scientist\n\n"
        "Format de réponse (obligatoire, JSON strict) :\n{\"reponse\": SCORE}\n\nOffres : "
    )
    config = AppConfig.model_validate({"llm": {"prompt_score": old_prompt}})
    assert config.llm.search_criteria == "Ce que je veux :\n- Data scientist"


def test_prompt_complet_contient_bareme_et_criteres():
    from jobfinder.llm import build_prompt
    prompt = build_prompt("Je veux du ML", "Data Scientist", "EDF", "Description")
    assert "Je veux du ML" in prompt and "0 à 19" in prompt and '"reponse"' in prompt
    assert prompt.rstrip().endswith("Description")
