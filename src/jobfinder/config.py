"""Lecture, validation et sauvegarde de la configuration (config.json).

La configuration est décrite par des modèles pydantic : chaque champ a un type et
une valeur par défaut. Avantages par rapport à un simple dictionnaire :
    - un champ absent du fichier prend automatiquement sa valeur par défaut ;
    - une valeur invalide (ex : llm.provider = "toto") lève une erreur explicite ;
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
import re
import shutil
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv, set_key
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobfinder.paths import CONFIG_PATH, DEFAULT_CONFIG_PATH, ENV_PATH

logger = logging.getLogger(__name__)

# Clés courtes des plateformes (utilisées dans config.json et dans la base)
PLATFORM_KEYS = ("linkedin", "apec", "hw", "ft", "sp")

LlmProvider = Literal["Local", "ChatGPT", "Mistral"]


class _Section(BaseModel):
    """Base commune : les clés inconnues du JSON sont ignorées sans erreur."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


class PreFilterConfig(_Section):
    """Filtre par mots avant l'appel au LLM (gratuit et instantané)."""
    enabled: bool = False
    blacklist: list[str] = Field(default_factory=list)  # un mot présent -> offre écartée
    whitelist: list[str] = Field(default_factory=list)  # si non vide, un de ces mots est requis


def strip_format_instructions(prompt: str) -> str:
    """Retire d'un ancien prompt complet la partie « format de réponse JSON ».

    Cette partie est désormais fixée dans le code (llm.py) : l'utilisateur
    n'écrit plus que ses critères de recherche.
    """
    lower = prompt.lower()
    positions = [lower.find(marker) for marker in FORMAT_MARKERS if marker in lower]
    criteria = prompt[:min(positions)] if positions else prompt
    criteria = re.sub(r"\s*Offres?\s*:\s*$", "", criteria.strip())  # ancien "Offres :" final
    return criteria.strip()


# Début de la partie "format de réponse" dans les anciens prompts
FORMAT_MARKERS = ("format de réponse", "répond en donnant", "réponds en donnant", "au format json")


class LlmConfig(_Section):
    provider: LlmProvider = "Local"
    ollama_model: str = "gemma4:26b"  # modèle utilisé avec le provider "Local"
    # Les clés API ne sont PAS ici : elles sont dans le fichier .env (voir get_api_key)

    # Critères de recherche rédigés par l'utilisateur (ce qu'il veut, tolère, refuse).
    # Le barème 0-100 et le format de réponse sont ajoutés automatiquement (llm.py).
    search_criteria: str = ""

    # Seuil de pertinence : une offre dont le score est < seuil est "écartée par l'IA".
    # Le seuil est appliqué à l'affichage : le modifier fait réapparaître (ou disparaître)
    # des offres dans "Nouvelles offres" sans relancer le LLM.
    score_threshold: int = Field(default=50, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def _migrate_old_prompt(cls, data):
        """Ancien config.json : `prompt_score` (prompt complet) -> `search_criteria`."""
        if isinstance(data, dict) and not data.get("search_criteria") and data.get("prompt_score"):
            data = {**data, "search_criteria": strip_format_instructions(data["prompt_score"])}
        return data


class AppConfig(_Section):
    keywords: list[str] = Field(default_factory=list)
    url: dict[str, str] = Field(default_factory=dict)
    launch_scrap: dict[str, bool] = Field(default_factory=dict)

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
        """Clés des plateformes cochées pour le scraping (les plateformes abandonnées sont ignorées)."""
        return [key for key, active in self.launch_scrap.items() if active and key in PLATFORM_KEYS]

    def scraping_errors(self) -> list[str]:
        """Liste des problèmes empêchant de lancer le scraping (vide si tout va bien)."""
        errors = []
        if not any(k.strip() for k in self.keywords):
            errors.append("Aucun mot-clé renseigné.")
        if not self.active_platforms():
            errors.append("Aucune plateforme cochée.")
        for key in self.active_platforms():
            if not self.url.get(key):
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
