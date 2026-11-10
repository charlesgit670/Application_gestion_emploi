import time
import re
import pandas as pd
import json
import functools
import threading
import urllib.parse
from selenium import webdriver
from aiolimiter import AsyncLimiter
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import backoff
from ollama import generate
from pydantic import BaseModel
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

class Format(BaseModel):
    reponse: int
    justification: str

def measure_time(func):
    """Annotation pour mesurer le temps d'exécution d'une fonction"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Démarre le chrono
        result = func(*args, **kwargs)
        end_time = time.time()  # Arrête le chrono
        execution_time = end_time - start_time

        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            print(f"Temps d'exécution de {class_name}.{func.__name__}: {execution_time:.2f} secondes")
        else:
            print(f"Temps d'exécution de {func.__name__}: {execution_time:.2f} secondes")

        # print(f"Temps d'exécution de {func.__name__}: {execution_time:.2f} secondes")
        return result
    return wrapper

# Verrou + cache pour éviter la race condition ChromeDriverManager en multithreading
_driver_path_lock = threading.Lock()
_driver_path = None

# On limite à 1 requête par seconde (ou légèrement moins pour être sûr, ex: 1 req / 1.1 sec)
# À ajuster selon les limites exactes du free tier pour le modèle choisi
rate_limiter = AsyncLimiter(1, 1.1)

# Fonction pour créer un driver
def create_driver():
    global _driver_path
    with _driver_path_lock:
        if _driver_path is None:
            _driver_path = ChromeDriverManager().install()

    options = Options()
    # options.add_argument("user-data-dir=C:\\Users\\charles\\AppData\\Local\\Google\\Chrome\\User Data")
    options.add_argument("--headless")  # Mode headless
    options.add_argument("--disable-gpu")  # Recommandé pour éviter certains bugs en mode headless
    options.add_argument("--window-size=1920x1080")  # Taille de la fenêtre (facultatif)
    options.add_argument("--no-sandbox")  # Utile dans certains environnements Linux
    options.add_argument("--disable-dev-shm-usage")  # Évite certains problèmes de mémoire

    driver = webdriver.Chrome(service=Service(_driver_path), options=options)
    return driver

def normalize_keywords(keywords):
    cleaned = []
    seen = set()
    for keyword in keywords or []:
        if keyword is None:
            continue
        value = str(keyword).strip()
        if not value:
            continue
        lower = value.lower()
        if lower in seen:
            continue
        seen.add(lower)
        cleaned.append(value)
    return cleaned

def _encode_keyword(value, encode_mode):
    if encode_mode == "query":
        return urllib.parse.quote_plus(value)
    if encode_mode == "path":
        return urllib.parse.quote(value, safe="")
    raise ValueError(f"encode_mode inconnu: {encode_mode}")

def build_keyword_terms(keywords, mode="one_by_one", quote_terms_for_or=False):
    """Construit la ou les chaînes de mots clés (non encodées) selon le mode choisi.
    """
    clean_keywords = normalize_keywords(keywords)
    if not clean_keywords:
        return []
    if mode == "one_by_one":
        return clean_keywords
    elif mode == "or":
        if quote_terms_for_or:
            joined = " OR ".join([f"\"{kw}\"" for kw in clean_keywords])
        else:
            joined = " OR ".join(clean_keywords)
        return [joined]
    elif mode == "all":
        return [" ".join(clean_keywords)]
    else:
        raise ValueError(f"keyword mode inconnu: {mode}")

def build_keyword_urls(base_url, keywords, mode="one_by_one", encode_mode="query", quote_terms_for_or=False):
    if "{keyword}" not in base_url:
        raise ValueError("Le template d'URL doit contenir {keyword}.")
    terms = build_keyword_terms(keywords, mode=mode, quote_terms_for_or=quote_terms_for_or)
    if not terms:
        return []
    return [base_url.format(keyword=_encode_keyword(term, encode_mode)) for term in terms]

# Throttle proactif dédié à ChatGPT (indépendant de rate_limiter, réservé à Mistral) :
# le sleep(0.5) qui s'appliquait après chaque appel LLM, quel que soit le provider, a
# été retiré lors du passage à l'async ; on le remplace ici pour ne pas se reposer
# uniquement sur le retry réactif côté ChatGPT.
chatgpt_rate_limiter = AsyncLimiter(3, 1)

# Semaphore + sleep(1.1) évitent proactivement les 429 (free tier Mistral : 1 req/s).
# Le backoff est un filet de sécurité : full_jitter désynchronise les retries
# entre threads, max_time=120 laisse suffisamment de marge en cas de congestion.
@backoff.on_exception(backoff.expo, Exception, max_time=120, jitter=backoff.full_jitter)
async def add_LLM_comment(client_LLM, llm_config, row):
    """
    Modifier l'instruction_scoring en fonction de ce que vous recherchez
    """
    # Guard: si score existe déjà, sauter le traitement (évite double-traitement)
    if pd.notna(row.get('score')) and row.get('score') != -1:
        return row

    title = row["title"]
    company = row["company"]
    description = row["content"]
    offer_text = "\n".join([company, title, description])
    score_prompt = llm_config["prompt_score"] + "\n" + offer_text

    if llm_config["provider"] == "Local":
        format_spec = {
            "type": "object",
            "properties": {
                "reponse": {"type": "number"},
                "justification": {"type": "string"},
            }
        }
        response = generate(
            model="gemma4:26b",
            think=False,
            options={"temperature": 0.1},
            format=format_spec,
            prompt=score_prompt,
        )
        json_output = json.loads(response.response)
    elif llm_config["provider"] == "ChatGPT":
        async with chatgpt_rate_limiter:
            response = client_LLM.responses.parse(
                model="gpt-4o-mini",
                instructions=llm_config["prompt_score"],
                temperature=0.1,
                input=offer_text,
                text_format=Format
            )
        json_output = json.loads(response.output_text)
    elif llm_config["provider"] == "Mistral":
        async with rate_limiter:
            chat_response = await client_LLM.chat.complete_async(
                model="mistral-small-latest",
                temperature=0.1,
                messages=[{"role": "user", "content": score_prompt}],
                response_format={"type": "json_object"}
            )
        json_output = json.loads(chat_response.choices[0].message.content)

    row["is_good_offer"] = 1 if int(json_output["reponse"]) >= 50 else 0
    row["comment"] = json_output["justification"]
    row["score"] = int(json_output["reponse"])

    return row

async def add_LLM_comment_and_track_progress(client, llm_config, row, i, total, progress_dict):
    try:
        result = await add_LLM_comment(client, llm_config, row)
    except Exception as e:
        print(f"[LLM ERROR] add_LLM_comment échoué : {type(e).__name__}: {e}")
        result = row
    finally:
        # Use total if total > 0 else 1 to prevent division-by-zero
        safe_total = total if total and total > 0 else 1
        progress_dict["Traitement des nouvelles offres (LLM)"] = (i + 1, safe_total)
    return result

def is_language_allowed(languages_config, content):
    try:
        langue = detect(content)
    except LangDetectException:
        return languages_config.get("autre", False)
    if langue in languages_config:
        return languages_config[langue]
    return languages_config.get("autre", False)

