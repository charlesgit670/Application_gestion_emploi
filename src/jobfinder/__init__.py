"""JobFinder : scraping d'offres d'emploi, filtrage par LLM et suivi des candidatures.

Organisation du paquet :
    paths.py    chemins du projet (indépendants du dossier de lancement)
    config.py   lecture / écriture / validation de config.json
    models.py   statuts d'une offre, noms de colonnes, règles de pertinence
    storage.py  base SQLite (lecture, insertion, changements de statut)
    logs.py     configuration du logging
"""
