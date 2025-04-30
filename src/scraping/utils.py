import time
import re
import json
import functools
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import backoff



def measure_time(func):
    """Annotation pour mesurer le temps d'exécution d'une fonction"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Démarre le chrono
        result = func(*args, **kwargs)
        end_time = time.time()  # Arrête le chrono
        execution_time = end_time - start_time
        print(f"Temps d'exécution de {func.__name__}: {execution_time:.2f} secondes")
        return result
    return wrapper

# Fonction pour créer un driver
def create_driver():

    options = Options()
    # options.add_argument("user-data-dir=C:\\Users\\charles\\AppData\\Local\\Google\\Chrome\\User Data")
    options.add_argument("--headless")  # Mode headless
    options.add_argument("--disable-gpu")  # Recommandé pour éviter certains bugs en mode headless
    options.add_argument("--window-size=1920x1080")  # Taille de la fenêtre (facultatif)
    options.add_argument("--no-sandbox")  # Utile dans certains environnements Linux
    options.add_argument("--disable-dev-shm-usage")  # Évite certains problèmes de mémoire

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

@backoff.on_exception(backoff.expo, Exception)
def add_LLM_comment(client_LLM, row):
    """
    Modifier l'intruction en fonction de ce que vous recherchez
    """

    instruction = """
        Je suis a la recherche d'un CDI en tant que data scientist :
        Ce que je veux :
        - Forte part de création de modèle de machine learning et modèle statistique
        - Analyser et comprendre le résultat des modèles
        - Préférence pour le secteur industriel comme l'énergie, l'écologie
        - Utilisation du langage Python

        Ce que je tolère :
        - Préparation des données
        - Industrialisation de modèles
        - Présentation des résultats

        Ce que je ne veux pas :
        - Stage et alternance
        - Un poste qui ressemble plus à data analyste ou data engineer
        - Les secteurs bancaire, assurance, retails etc.

        Ceux sont des préférences donc ne soit pas trop exigeant

        Est-ce que l'offre ci-dessus pourrait correspondre à mes attentes ?
        Répond en donnant un score d'interet pour l'offre entre 0 et 100 :
        - moins de 50 si l'offre contient très peu de tache lié au machine learning 
        - supérieur à 50 si des fortes part de machine learning 
        et justifie ton choix en énumérant tes arguments en quelques mots tout ça au format json suivant:
        {
        "reponse": "score",
        "justification": "Ta justification"
        }

        Offres : 
        """

    title = row["title"]
    company = row["company"]
    description = row["content"]

    response = client_LLM.responses.create(
        model="gpt-4o-mini",
        instructions=instruction,
        temperature=0,
        input=company + "\n" + title + "\n" + description,
    )


    # response = client_LLM.chat.complete(
    #     model="mistral-large-latest",
    #     temperature=0,
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": instruction + "\n" + company + "\n" + title + "\n" + description,
    #         },
    #     ]
    # )

    # Utiliser une regex pour extraire ce qui est entre { }
    match = re.search(r'\{.*\}', response.output_text, re.DOTALL)
    if match:
        json_string = match.group(0)
        data = json.loads(json_string)
        row["is_good_offer"] = 1 if int(data["reponse"]) >= 50 else 0
        row["comment"] = data["justification"]
        row["score"] = int(data["reponse"])
    else:
        print("!!! Error LLM response !!!")
        print(response.output_text)

    return row
