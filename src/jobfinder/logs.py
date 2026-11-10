"""Configuration du logging (remplace les print).

Usage dans chaque module :
    import logging
    logger = logging.getLogger(__name__)
    logger.info("message")

Les messages vont dans la console ET dans data/jobfinder.log.
"""
import logging

from jobfinder.paths import LOG_PATH

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure le logging une seule fois pour toute l'application."""
    root = logging.getLogger()
    if root.handlers:  # déjà configuré (ex : rechargement de module)
        return

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=LOG_FORMAT, handlers=handlers)

    # Bibliothèques trop bavardes en INFO
    for noisy in ("httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
