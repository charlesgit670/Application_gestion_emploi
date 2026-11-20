"""Construction des URLs de recherche à partir des mots-clés.

Trois modes, fixés par plateforme dans chaque scraper (attribut keyword_mode) selon
ce que le site sait faire :
    one_by_one : une recherche par mot-clé       ["data scientist", "machine learning"]
    or         : une seule recherche avec OR     ["data scientist OR machine learning"]
    all        : une seule recherche, tout collé ["data scientist machine learning"]

Exemple :
    build_keyword_urls("https://site.fr/?q={keyword}", ["data", "ml"], mode="or")
    -> ["https://site.fr/?q=data+OR+ml"]
"""
import urllib.parse


def normalize_keywords(keywords: list[str]) -> list[str]:
    """Retire les mots-clés vides et les doublons (sans tenir compte de la casse)."""
    cleaned, seen = [], set()
    for keyword in keywords or []:
        value = str(keyword or "").strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            cleaned.append(value)
    return cleaned


def build_keyword_terms(keywords: list[str], mode: str = "one_by_one", quote_terms_for_or: bool = False) -> list[str]:
    """Texte(s) de recherche, non encodé(s), selon le mode choisi."""
    clean = normalize_keywords(keywords)
    if not clean:
        return []
    if mode == "one_by_one":
        return clean
    if mode == "or":
        terms = [f'"{kw}"' for kw in clean] if quote_terms_for_or else clean
        return [" OR ".join(terms)]
    if mode == "all":
        return [" ".join(clean)]
    raise ValueError(f"Mode de mots-clés inconnu : {mode}")


def build_keyword_urls(url_template: str, keywords: list[str], mode: str = "one_by_one",
                       encode_mode: str = "query", quote_terms_for_or: bool = False) -> list[str]:
    """URLs de recherche à partir d'un modèle contenant {keyword}.

    encode_mode :
        "query" -> le mot-clé est dans les paramètres (?q=data+scientist)
        "path"  -> le mot-clé est dans le chemin       (/mot-cles/data%20scientist/)
    """
    if "{keyword}" not in url_template:
        raise ValueError("Le modèle d'URL doit contenir {keyword}.")
    if encode_mode == "query":
        encode = urllib.parse.quote_plus
    elif encode_mode == "path":
        encode = lambda value: urllib.parse.quote(value, safe="")  # noqa: E731
    else:
        raise ValueError(f"encode_mode inconnu : {encode_mode}")

    terms = build_keyword_terms(keywords, mode, quote_terms_for_or)
    return [url_template.format(keyword=encode(term)) for term in terms]
