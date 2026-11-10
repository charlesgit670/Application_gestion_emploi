"""Lancer UN scraper seul, pour le déboguer. Rien n'est écrit dans la base.

En ligne de commande, depuis le dossier src/ :
    python -m jobfinder.scrapers ft                         # France Travail, réglages de config.json
    python -m jobfinder.scrapers ft --max-details 3         # ne lit que 3 fiches détaillées
    python -m jobfinder.scrapers ft --keywords "data scientist" --days 3
    python -m jobfinder.scrapers --list                     # plateformes disponibles

Depuis PyCharm (points d'arrêt) : lancer debug_scraper.py à la racine du projet.
Depuis un notebook :
    from jobfinder.scrapers.__main__ import debug_scraper
    df = debug_scraper("ft", max_details=3)

Ce que produit une exécution, dans data/debug/<plateforme>_<date-heure>/ :
    - chaque page téléchargée (NNN_<code HTTP>_<adresse>.html), dans l'ordre :
      à ouvrir dans un navigateur ou un éditeur pour voir ce que le scraper a VRAIMENT reçu
      (souvent différent de ce qu'affiche le navigateur, qui exécute le JavaScript) ;
    - resultat.csv : les offres obtenues ;
    - le journal détaillé dans la console (chaque requête, chaque offre ignorée et pourquoi).
"""
import argparse
import logging
from datetime import datetime

import pandas as pd

from jobfinder.config import load_config
from jobfinder.logs import setup_logging
from jobfinder.models import Col
from jobfinder.paths import DATA_DIR
from jobfinder.scrapers import SCRAPERS

logger = logging.getLogger("jobfinder.debug")


def debug_scraper(key: str, keywords: list[str] | None = None, days: int | None = None,
                  max_details: int | None = None, save_html: bool = True) -> pd.DataFrame:
    """Exécute le scraper `key` avec la configuration de config.json, éventuellement modifiée.

    keywords    : remplace les mots-clés de la configuration
    days        : remplace l'ancienneté maximale des offres
    max_details : nombre maximum de fiches détaillées lues (essais rapides)
    save_html   : sauvegarde chaque page téléchargée dans data/debug/
    """
    config = load_config()
    if keywords:
        config.keywords = keywords
    if days:
        config.filter_day_scrap = days

    scraper = SCRAPERS[key](config)
    scraper.max_details = max_details
    output_dir = DATA_DIR / "debug" / f"{key}_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    output_dir.mkdir(parents=True, exist_ok=True)
    if save_html:
        scraper.debug_dir = output_dir

    logger.info("Scraper %s | mots-clés : %s | mode : %s | %d jour(s)",
                scraper.label, config.keywords, scraper.keyword_mode, config.filter_day_scrap)
    if hasattr(scraper, "search_urls"):
        for url in scraper.search_urls():
            logger.info("URL de recherche : %s", url)
    if key == "apec":
        logger.info("APEC tourne dans un processus séparé : pas de sauvegarde HTML ni de limite "
                    "de fiches. Pour le déboguer : python -m jobfinder.scrapers.apec_worker < ../config.json")

    df = scraper.run(progress=lambda current, total: logger.debug("Fiches lues : %d / %d", current, total))
    df.to_csv(output_dir / "resultat.csv", sep=";", index=False, encoding="utf-8-sig")

    print_summary(df, output_dir)
    return df


def print_summary(df: pd.DataFrame, output_dir) -> None:
    print("\n" + "=" * 70)
    print(f"{len(df)} offre(s) complète(s) obtenue(s)")
    if not df.empty:
        lengths = df[Col.CONTENT].str.len()
        print(f"Description : {lengths.min()} à {lengths.max()} caractères "
              f"(médiane {int(lengths.median())})")
        print(f"Dates inconnues : {df[Col.PUBLISHED_ON].isna().sum()}")
        for row in df.head(5).itertuples():
            print(f"  - {row.title[:50]:<50} | {row.company[:25]:<25} | {row.published_on}")
    print(f"Pages HTML et resultat.csv : {output_dir}")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lancer un scraper seul pour le déboguer (rien n'est écrit en base).")
    parser.add_argument("platform", nargs="?", choices=sorted(SCRAPERS), help="clé de la plateforme")
    parser.add_argument("--keywords", nargs="+", help="mots-clés à utiliser à la place de ceux de config.json")
    parser.add_argument("--days", type=int, help="ancienneté maximale des offres (jours)")
    parser.add_argument("--max-details", type=int, help="nombre maximum de fiches détaillées lues")
    parser.add_argument("--no-html", action="store_true", help="ne pas sauvegarder les pages HTML")
    parser.add_argument("--list", action="store_true", help="afficher les plateformes disponibles")
    args = parser.parse_args()

    if args.list or not args.platform:
        for key, scraper in sorted(SCRAPERS.items()):
            print(f"{key:<10} {scraper.label}")
        return

    setup_logging(logging.DEBUG)
    debug_scraper(args.platform, args.keywords, args.days, args.max_details, save_html=not args.no_html)


if __name__ == "__main__":
    main()
