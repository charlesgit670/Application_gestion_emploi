"""Évaluation des offres par un LLM : un score de 0 à 100 et une justification.

Trois fournisseurs, une seule interface :
    scorer = LlmScorer(config.llm)
    verdict = await scorer.score(title="Data Scientist", company="EDF", content="...")
    verdict.score, verdict.justification

Choix de conception :
    - Les trois clients sont ASYNCHRONES (AsyncOpenAI, Mistral.complete_async,
      ollama.AsyncClient) : l'interface reste fluide pendant l'évaluation.
    - Débit limité par fournisseur (aiolimiter) pour éviter les erreurs 429.
    - Nouvelles tentatives UNIQUEMENT sur les erreurs temporaires (réseau, 429, 5xx).
      Une réponse illisible n'est pas réessayée : l'offre reste « non évaluée » et
      sera reproposée au LLM au prochain scraping (règle R6).
"""
import asyncio
import json
import logging
import re

import backoff
import httpx
from aiolimiter import AsyncLimiter

from jobfinder.config import LlmConfig, get_api_key

logger = logging.getLogger(__name__)

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}

OPENAI_MODEL = "gpt-4o-mini"
MISTRAL_MODEL = "mistral-small-latest"
TEMPERATURE = 0.1

# Format de sortie demandé au LLM (JSON schema), utilisé par Ollama et ChatGPT
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {"reponse": {"type": "integer"}, "justification": {"type": "string"}},
    "required": ["reponse", "justification"],
    "additionalProperties": False,
}

# Réglages par fournisseur : requêtes simultanées et débit maximum (requêtes / seconde)
PROVIDER_LIMITS = {
    "Local": {"concurrency": 1, "rate": None},     # un seul GPU : une offre à la fois
    "ChatGPT": {"concurrency": 5, "rate": (3, 1)},  # 3 requêtes par seconde
    "Mistral": {"concurrency": 2, "rate": (1, 1.1)},  # offre gratuite : ~1 requête par seconde
}


class LlmError(Exception):
    """Réponse du LLM inexploitable (pas de JSON, score manquant...)."""


class Verdict:
    """Résultat de l'évaluation d'une offre."""

    def __init__(self, score: int, justification: str):
        self.score = max(0, min(100, int(score)))  # borné à [0, 100]
        self.justification = justification.strip()

    def __repr__(self) -> str:
        return f"Verdict(score={self.score}, justification={self.justification[:40]!r})"


def parse_verdict(text: str) -> Verdict:
    """Lit la réponse JSON du LLM : {"reponse": 75, "justification": "..."}.

    Tolère les blocs ```json```, un texte autour du JSON et un score écrit en texte ("75").
    """
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise LlmError(f"Pas de JSON dans la réponse : {text[:100]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LlmError(f"JSON invalide : {exc}") from exc

    raw_score = data.get("reponse", data.get("score"))
    number = re.search(r"\d+", str(raw_score)) if raw_score is not None else None
    if number is None:
        raise LlmError(f"Score absent de la réponse : {data}")
    return Verdict(int(number.group(0)), str(data.get("justification", "")))


def is_transient(exc: BaseException) -> bool:
    """Vrai si l'erreur est temporaire et mérite une nouvelle tentative."""
    if isinstance(exc, (httpx.TransportError, asyncio.TimeoutError)):
        return True
    if type(exc).__name__ in ("APIConnectionError", "APITimeoutError", "NoResponseError"):
        return True
    return getattr(exc, "status_code", None) in TRANSIENT_STATUS


def build_prompt(prompt_score: str, title: str, company: str, content: str) -> str:
    """Offre présentée au LLM après les consignes (même format que l'ancienne version)."""
    return f"{prompt_score}\n{company}\n{title}\n{content}"


class LlmScorer:
    """Évalue des offres avec le fournisseur choisi dans la configuration."""

    def __init__(self, llm_config: LlmConfig):
        self.config = llm_config
        self.provider = llm_config.provider
        limits = PROVIDER_LIMITS[self.provider]
        self._semaphore = asyncio.Semaphore(limits["concurrency"])
        self._limiter = AsyncLimiter(*limits["rate"]) if limits["rate"] else None
        self._client = self._create_client()

    def _create_client(self):
        """Client du fournisseur (import local : seul le SDK utilisé est chargé)."""
        if self.provider == "Local":
            from ollama import AsyncClient
            return AsyncClient()

        api_key = get_api_key(self.provider)
        if not api_key:
            raise LlmError(f"Clé API {self.provider} absente : renseignez-la dans la configuration (.env).")
        if self.provider == "ChatGPT":
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=api_key)
        from mistralai.client import Mistral
        return Mistral(api_key=api_key)

    async def score(self, title: str, company: str, content: str) -> Verdict:
        """Évalue une offre. Lève LlmError (réponse illisible) ou l'erreur du SDK."""
        prompt = build_prompt(self.config.prompt_score, title, company, content)
        async with self._semaphore:
            text = await self._ask_with_retry(prompt)
        return parse_verdict(text)

    @backoff.on_exception(backoff.expo, Exception, giveup=lambda e: not is_transient(e),
                          max_time=120, jitter=backoff.full_jitter)
    async def _ask_with_retry(self, prompt: str) -> str:
        if self._limiter is None:
            return await self._ask(prompt)
        async with self._limiter:
            return await self._ask(prompt)

    async def _ask(self, prompt: str) -> str:
        """Un appel au LLM ; renvoie le texte brut de la réponse."""
        if self.provider == "Local":
            response = await self._client.generate(
                model=self.config.ollama_model, prompt=prompt, format=VERDICT_SCHEMA,
                think=False, options={"temperature": TEMPERATURE},
            )
            return response.response

        if self.provider == "ChatGPT":
            response = await self._client.responses.create(
                model=OPENAI_MODEL, input=prompt, temperature=TEMPERATURE,
                text={"format": {"type": "json_schema", "name": "verdict", "schema": VERDICT_SCHEMA, "strict": True}},
            )
            return response.output_text

        response = await self._client.chat.complete_async(
            model=MISTRAL_MODEL, temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
