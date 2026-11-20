"""Scraping APEC exécuté dans un processus séparé (lancé par scrapers/apec.py).

Pourquoi un processus séparé ?
    APEC est protégé par un antibot : il faut un vrai navigateur (Firefox piloté par
    Playwright). L'API synchrone de Playwright refuse de tourner dans un thread qui
    possède déjà une boucle asyncio, ce qui est le cas dans l'application. Un processus
    à part l'isole complètement et permet de scraper APEC en parallèle des autres sites.

Protocole d'échange avec le processus parent :
    entrée  (stdin)  : la configuration, en JSON
    sortie  (stdout) : une ligne JSON par message
        {"progress": [3, 40]}     avancement
        {"jobs": [{...}, ...]}    résultat final
    journal (stderr) : les logs, affichés dans la console du parent

Lancement manuel pour tester (depuis le dossier src/) :
    python -m jobfinder.scrapers.apec_worker < ../config.json
"""
import json
import logging
import random
import re
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta

from playwright.sync_api import Page, sync_playwright

from jobfinder.scrapers.keywords import build_keyword_terms

logger = logging.getLogger("apec_worker")

HOME_URL = "https://www.apec.fr/"
SEARCH_API = "https://www.apec.fr/cms/webservices/rechercheOffre"
DETAIL_API = "https://www.apec.fr/cms/webservices/offre/public?numeroOffre={}"
OFFER_URL = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{}"
PAGE_SIZE = 20
SESSION_RESET_EVERY = 50      # nouvelle session après N fiches lues
MAX_CONSECUTIVE_FAILURES = 3  # nouvelle session après N échecs d'affilée

ANTIBOT_PASSED_JS = "() => !document.body.innerText.includes('Please enable JS') && document.body.innerText.length > 0"

# Requête POST exécutée DANS la page, pour bénéficier des cookies de la session antibot
POST_JSON_JS = """
async ([url, payload]) => {
    const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json'},
        body: JSON.stringify(payload),
        credentials: 'include',
    });
    return response.ok ? await response.json() : null;
}
"""


def send(message: dict) -> None:
    """Envoie un message JSON au processus parent."""
    print(json.dumps(message, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------------------
# Paramètres de recherche
# ---------------------------------------------------------------------------
def parse_search_url(url: str) -> dict:
    """Extrait les filtres de l'URL de recherche APEC copiée depuis le site."""
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    distance = params.get("distance", ["0"])[0]
    return {
        "lieux": params.get("lieux", []),
        "typesConvention": params.get("typesConvention", []),
        "typesContrat": params.get("typesContrat", []),
        "distance": int(distance) if distance.isdigit() else 0,
    }


def build_payload(filters: dict, search_terms: str, start_index: int, geo: dict | None) -> dict:
    """Corps de la requête de recherche APEC."""
    payload = {
        "lieux": filters["lieux"],
        "typeClient": "CADRE",
        "sorts": [{"type": "DATE", "direction": "DESCENDING"}],
        "pagination": {"range": PAGE_SIZE, "startIndex": start_index},
        "activeFiltre": True,
        "motsCles": search_terms,
    }
    if filters["typesContrat"]:
        payload["typesContrat"] = filters["typesContrat"]
    if filters["typesConvention"]:
        payload["typesConvention"] = filters["typesConvention"]
    # Sans coordonnées GPS, APEC ignore le rayon et renvoie des offres hors zone
    if filters["distance"] > 0 and geo:
        payload["pointGeolocDeReference"] = {"distance": str(filters["distance"]), **geo}
    return payload


def parse_apec_date(raw) -> date | None:
    """APEC renvoie selon les cas un timestamp en ms, une date ISO ou JJ/MM/AAAA."""
    if raw is None:
        return None
    value = str(raw).strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000).date()
    for text, fmt in ((value[:10], "%Y-%m-%d"), (value, "%d/%m/%Y")):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def html_to_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Navigateur
# ---------------------------------------------------------------------------
def open_session(page: Page) -> None:
    """Charge la page d'accueil et attend que l'antibot laisse passer."""
    page.goto(HOME_URL, wait_until="networkidle")
    time.sleep(3)
    try:
        page.wait_for_function(ANTIBOT_PASSED_JS, timeout=30_000)
        logger.info("Session APEC ouverte")
    except Exception:
        logger.warning("Session APEC : vérification antibot non confirmée, on continue")


def fetch_geo(page: Page, filters: dict) -> dict | None:
    """Coordonnées GPS du lieu recherché, lues sur une offre de ce lieu (APEC ne les fournit pas)."""
    if not filters["lieux"]:
        return None
    payload = {
        "lieux": [filters["lieux"][0]], "typeClient": "CADRE",
        "sorts": [{"type": "DATE", "direction": "DESCENDING"}],
        "pagination": {"range": 1, "startIndex": 0}, "activeFiltre": True,
    }
    data = page.evaluate(POST_JSON_JS, [SEARCH_API, payload]) or {}
    results = data.get("resultats") or []
    if results and results[0].get("latitude") and results[0].get("longitude"):
        return {"latitude": float(results[0]["latitude"]), "longitude": float(results[0]["longitude"])}
    logger.warning("Coordonnées du lieu %s introuvables : le rayon sera ignoré", filters["lieux"][0])
    return None


def search_offers(page: Page, filters: dict, terms: list[str], max_age_days: int, geo: dict | None) -> list[dict]:
    """Liste des offres (sans description) pour chaque recherche, triées de la plus récente."""
    date_limit = date.today() - timedelta(days=max_age_days)
    offers: dict[str, dict] = {}

    for search_terms in terms:
        start = 0
        while True:
            data = page.evaluate(POST_JSON_JS, [SEARCH_API, build_payload(filters, search_terms, start, geo)])
            results = (data or {}).get("resultats") or []
            too_old = False
            for result in results:
                published_on = parse_apec_date(result.get("datePublication"))
                if published_on is not None and published_on < date_limit:
                    too_old = True  # résultats triés par date : la suite est encore plus ancienne
                    break
                number = result.get("numeroOffre")
                if number and result.get("intitule") and result.get("nomCommercial"):
                    offers.setdefault(number, {
                        "source_id": number,
                        "title": result["intitule"],
                        "company": result["nomCommercial"],
                        "link": OFFER_URL.format(number),
                        "published_on": published_on.isoformat() if published_on else None,
                    })
            if too_old or len(results) < PAGE_SIZE:
                break
            start += PAGE_SIZE
            time.sleep(random.uniform(0.5, 1.0))

    return list(offers.values())


def read_offer_detail(page: Page, number: str) -> str:
    """Description complète d'une offre (texte du poste + entreprise + profil)."""
    page.goto(DETAIL_API.format(number), wait_until="domcontentloaded")
    # En cas de captcha, on laisse jusqu'à 60 s à l'antibot pour se résoudre
    page.wait_for_function(ANTIBOT_PASSED_JS, timeout=60_000)
    detail = json.loads(page.evaluate("() => document.body.innerText"))
    parts = [detail.get(key) or "" for key in ("texteHtml", "texteHtmlEntreprise", "texteHtmlProfil")]
    return html_to_text("\n\n".join(p for p in parts if p))


def read_all_details(page: Page, offers: list[dict]) -> list[dict]:
    """Ajoute la description à chaque offre, en renouvelant la session si besoin."""
    complete, failures = [], 0
    for i, offer in enumerate(offers, start=1):
        if i > 1 and (i % SESSION_RESET_EVERY == 0 or failures >= MAX_CONSECUTIVE_FAILURES):
            logger.info("Renouvellement de la session APEC (%d/%d)", i, len(offers))
            open_session(page)
            failures = 0
        try:
            offer["content"] = read_offer_detail(page, offer["source_id"])
            complete.append(offer)
            failures = 0
        except Exception as exc:
            failures += 1
            logger.warning("APEC : échec sur l'offre %s (%s)", offer["source_id"], exc)
            time.sleep(3)
        send({"progress": [i, len(offers)]})
    return complete


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    config = json.load(sys.stdin)

    filters = parse_search_url(config["url"]["apec"])
    # APEC accepte l'opérateur OR : une seule recherche pour tous les mots-clés
    terms = build_keyword_terms(config["keywords"], "or", quote_terms_for_or=True)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True, firefox_user_prefs={"dom.webdriver.enabled": False})
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        try:
            open_session(page)
            geo = fetch_geo(page, filters)
            offers = search_offers(page, filters, terms, config["filter_day_scrap"], geo)
            logger.info("APEC : %d offre(s) trouvée(s), lecture des descriptions...", len(offers))
            send({"jobs": read_all_details(page, offers)})
        finally:
            browser.close()


if __name__ == "__main__":
    main()
