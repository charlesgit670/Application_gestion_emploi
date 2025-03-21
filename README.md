# Application de gestion de recherche d'emploi

## Objectif

L'application permet de scraper automatiquement plusieurs sites d'emploi et de gérer le suivi des offres récupérées.
Actuellement, seuls **Welcome to the Jungle** et **Apec** sont pris en charge.

## Comment l'utiliser

### Configuration de l'URL à scraper

Pour personnaliser les offres récupérées, il est nécessaire de modifier manuellement l'URL dans la méthode `__init__` des fichiers **`WelcomeToTheJungle.py`** et **`Apec.py`**. Cette URL doit correspondre aux filtres configurés sur le site concerné.

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
- Une brève description de l'offre.
- Des boutons **Suivant** et **Précédent**.
- Un bouton **Postuler**, qui classe l'offre dans "Candidatures en cours" et la retire de cette page.
- Un bouton **Marquer comme lu**, qui classe l'offre dans "Offres déjà lues" et la retire également.

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

