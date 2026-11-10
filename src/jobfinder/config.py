"""Lecture, validation et sauvegarde de la configuration (config.json).

La configuration est décrite par des modèles pydantic : chaque champ a un type et
une valeur par défaut. Avantages par rapport à un simple dictionnaire :
    - un champ absent du fichier prend automatiquement sa valeur par défaut ;
    - une valeur invalide (ex : keyword_mode = "toto") lève une erreur explicite ;
    - l'autocomplétion de l'IDE fonctionne (config.llm.provider, ...).

Le format JSON reste identique à l'existant : un ancien config.json se charge tel quel.

Exemple :
    config = load_config()
    config.llm.score_threshold = 60
    save_config(config)
"""
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv, set_key
from pydantic import BaseModel, ConfigDict, Field

from jobfinder.paths import CONFIG_PATH, DEFAULT_CONFIG_PATH, ENV_PATH

logger = logging.getLogger(__name__)

# Clés courtes des plateformes (utilisées dans config.json et dans la base)
PLATFORM_KEYS = ("wttj", "apec", "linkedin", "sp", "hw", "ft")

KeywordMode = Literal["one_by_one", "or", "all"]
LlmProvider = Literal["Local", "ChatGPT", "Mistral"]


class _Section(BaseModel):
    """Base commune : les clés inconnues du JSON sont ignorées sans erreur."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


class PreFilterConfig(_Section):
    """Filtre par mots avant l'appel au LLM (gratuit et instantané)."""
    enabled: bool = False
    blacklist: list[str] = Field(default_factory=list)  # un mot présent -> offre écartée
    whitelist: list[str] = Field(default_factory=list)  # si non vide, un de ces mots est requis


class LlmConfig(_Section):
    provider: LlmProvider = "Local"
    ollama_model: str = "gemma4:26b"  # modèle utilisé avec le provider "Local"
    # Les clés API ne sont PAS ici : elles sont dans le fichier .env (voir get_api_key)

    prompt_score: str = ""
    # Seuil de pertinence : une offre dont le score est < seuil est "écartée par l'IA".
    # Le seuil est appliqué à l'affichage : le modifier fait réapparaître (ou disparaître)
    # des offres dans "Nouvelles offres" sans relancer le LLM.
    score_threshold: int = Field(default=50, ge=0, le=100)


class AppConfig(_Section):
    keywords: list[str] = Field(default_factory=list)
    url: dict[str, str] = Field(default_factory=dict)
    launch_scrap: dict[str, bool] = Field(default_factory=dict)
    keyword_mode: dict[str, KeywordMode] = Field(default_factory=dict)

    filter_day_scrap: int = Field(default=7, ge=1)  # ancienneté max des offres scrapées
    language_filter: dict[str, bool] = Field(
        default_factory=lambda: {"fr": True, "en": False, "autre": False}
    )
    use_multithreading: bool = True
    use_llm: bool = False
    pre_filter: PreFilterConfig = Field(default_factory=PreFilterConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)

    # Suivi des candidatures : nombre de jours sans nouvelle avant de suggérer une relance
    follow_up_days: int = Field(default=10, ge=1)

    def active_platforms(self) -> list[str]:
        """Clés des plateformes cochées pour le scraping."""
        return [key for key, active in self.launch_scrap.items() if active]

    def scraping_errors(self) -> list[str]:
        """Liste des problèmes empêchant de lancer le scraping (vide si tout va bien)."""
        errors = []
        if not any(k.strip() for k in self.keywords):
            errors.append("Aucun mot-clé renseigné.")
        for key in self.active_platforms():
            if key not in PLATFORM_KEYS:
                errors.append(f"Plateforme inconnue : {key}")
            elif not self.url.get(key):
                errors.append(f"URL de recherche manquante pour {key}.")
        return errors


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """Charge config.json. Au premier lancement, il est créé depuis config_default.json."""
    load_dotenv(ENV_PATH)  # rend les clés de .env disponibles via os.getenv

    if not path.exists() and DEFAULT_CONFIG_PATH.exists():
        logger.info("Création de %s à partir de %s", path.name, DEFAULT_CONFIG_PATH.name)
        shutil.copy(DEFAULT_CONFIG_PATH, path)

    if not path.exists():
        return AppConfig()

    with open(path, encoding="utf-8") as f:
        return AppConfig.model_validate(json.load(f))


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    """Écrit la configuration dans config.json (indenté, accents conservés)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


# Nom de la variable d'environnement contenant la clé API de chaque provider
API_KEY_ENV_VARS = {"ChatGPT": "GPT_API_KEY", "Mistral": "MISTRAL_API_KEY"}


def get_api_key(provider: str) -> str:
    """Clé API d'un provider, lue dans les variables d'environnement (chargées depuis .env).

    Retourne "" pour Ollama (local, sans clé) ou si la clé n'est pas renseignée.
    """
    env_var = API_KEY_ENV_VARS.get(provider)
    return os.getenv(env_var, "") if env_var else ""


def set_api_key(provider: str, key: str, env_path: Path = ENV_PATH) -> None:
    """Enregistre la clé API d'un provider dans .env (le fichier est créé si besoin)."""
    env_var = API_KEY_ENV_VARS[provider]
    env_path.touch(exist_ok=True)
    set_key(env_path, env_var, key)
    os.environ[env_var] = key  # disponible immédiatement, sans redémarrer
