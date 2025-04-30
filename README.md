# Application de gestion de recherche d'emploi

## Objectif

L'application permet de scraper automatiquement plusieurs sites d'emploi et de gérer le suivi des offres récupérées.
Actuellement, seuls **Welcome to the Jungle** et **Apec** sont pris en charge.

## Comment l'utiliser

### Configuration de l'URL à scraper

Pour personnaliser les offres récupérées, il est nécessaire de modifier manuellement l'URL dans la méthode `__init__` des fichiers **`WelcomeToTheJungle.py`**,  **`Apec.py`** et **`Linkedin.py`**. Cette URL doit correspondre aux filtres configurés sur le site concerné.

### Ajout de la clé API ChatGPT

- Créer un fichier .env à la racine du projet et ajouter la clé comme ceci :
`OPENAI_API_KEY="your key"`
- Modifier le prompt de la variable `instruction` afin de l'adapter à vos critères dans le fichier `src/scraping/utils.py`

### Mise à jour des offres d'emploi

Pour mettre à jour les données, exécutez le script **`main.py`**, qui effectue les étapes suivantes :

1. Récupération des offres des sites d'emploi.
2. Identification des nouvelles offres en évitant les doublons en vérifiant :
   - Si le lien est identique.
   - Si la description du poste est similaire à plus de **95%**.
3. Sauvegarde des nouvelles offres.

> **Remarque :** En cas d'erreur, relancez **`main.py`** une seconde fois (l'origine du problème est inconnue pour l'instant).

## Lancer l'application Streamlit

Pour lancer l'application Streamlit, exécutez la commande suivante :
```sh
streamlit run src/application/app.py
```

## Fonctionnalités

### Nouvelles offres

![Nouvelles offres](imgs%2Fapp_new_job_img.png)

Sur la page d'accueil **"Nouvelles offres d'emploi"**, vous trouverez :

- Une pagination à gauche du titre (ex. **1/13**).
- L'intitulé du poste.
- Le nom de l'entreprise.
- Un lien vers l'offre sur le site source.
- Un score entre 0 et 100 indiquant le degré de pertinence de l'offre
- Commentaire écrit par le GPT
- Une brève description de l'offre.
- Des boutons **Suivant** et **Précédent**.
- Un bouton **Postuler**, qui classe l'offre dans "Candidatures en cours" et la retire de cette page.
- Un bouton **Marquer comme lu**, qui classe l'offre dans "Offres déjà lues" et la retire également.

### Offres filtrées par GPT

![app_unintesresting_job_img.png](imgs%2Fapp_unintesresting_job_img.png)

Dans l'onglet **"Offres filtrées par GPT""**, les offres ayant obtenues un score strictement inférieur à 50%

- Affichage du score
- Commentaire fait par GPT
- Vous pouvez afficher la description via un bouton déroulant.
- Le bouton **Restaurer** permet de replacer l'offre dans "Nouvelles offres".

### Offres déjà lues

![Offres déjà lues](imgs%2Fapp_already_seen_img.png)

Dans l'onglet **"Offres déjà lues"**, vous trouverez les offres marquées comme lues.

- Vous pouvez afficher la description via un bouton déroulant.
- Le bouton **Corbeille** permet de replacer l'offre dans "Nouvelles offres".

### Candidatures en cours

![Candidatures en cours](imgs%2Fapp_pending_img.png)

Dans l'onglet **"Candidatures en cours"**, vous retrouverez les offres pour lesquelles vous avez postulé.

- Le bouton **Corbeille** replace l'offre dans "Offres non lues".
- Le bouton **Refusé** classe l'offre dans "Candidatures refusées".

### Candidatures refusées

![Candidatures refusées](imgs%2Fapp_refused_img.png)

Dans l'onglet **"Candidatures refusées"**, vous trouverez les offres refusées.

- Un bouton **Restaurer** permet de replacer l'offre dans "Candidatures en cours".

