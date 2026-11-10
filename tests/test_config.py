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
