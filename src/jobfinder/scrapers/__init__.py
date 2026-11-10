"""Scrapers des sites d'emploi.

SCRAPERS associe la clé de config.json à la classe du scraper :
    scraper = SCRAPERS["hw"](config)
    df = scraper.run(progress=lambda current, total: print(current, total))
"""
from jobfinder.scrapers.apec import Apec
from jobfinder.scrapers.base import BaseScraper
from jobfinder.scrapers.francetravail import FranceTravail
from jobfinder.scrapers.hellowork import HelloWork
from jobfinder.scrapers.linkedin import Linkedin
from jobfinder.scrapers.servicepublic import ServicePublic

SCRAPERS: dict[str, type[BaseScraper]] = {
    scraper.key: scraper
    for scraper in (Linkedin, Apec, HelloWork, FranceTravail, ServicePublic)
}
