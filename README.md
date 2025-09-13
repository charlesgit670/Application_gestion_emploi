# Application de gestion de recherche d'emploi

## 🎯 Objectif

Cette application permet de **scraper automatiquement plusieurs sites d'emploi** et de **gérer le suivi des offres récupérées**.  
Elle propose également un **filtrage intelligent des offres via un LLM** (modèle de langage) grâce à un prompt adapté.  

Actuellement, trois plateformes sont supportées :  
- **LinkedIn**  
- **Welcome to the Jungle**  
- **Apec**

---

## ⚙️ Principe de fonctionnement

1. **Récupération** des offres depuis les sites d'emploi.  
2. **Détection des nouvelles offres** en évitant les doublons :  
   - Création d’un **hash unique** pour chaque offre (Plateforme + Titre + Entreprise + Description + Date de publication).  
   - Suppression des doublons.  
   - Comparaison avec la base existante pour ne garder que les nouvelles offres.  
3. **Sauvegarde** des nouvelles offres.  

---

## 🚀 Lancer l'application

1. Télécharger le projet.  
2. Installer les dépendances via le fichier `requirements.txt` dans votre environnement Python.  
3. Lancer l’application **Streamlit** depuis la racine du projet :  

   ```bash
   streamlit run src/app.py
   ```

4. (Optionnel) Créer un exécutable pour faciliter le lancement :  

   ```bash
   python setup.py build
   ```
   Cela génère un dossier `build` contenant `run.exe`, qui démarre directement le serveur Streamlit.

---

## 🔧 Configuration du Scraping

Sur la page **Mettre à jour les offres** :

![configuration_page.png](imgs%2Fconfiguration_page.png)

- **Sauvegarder la configuration** : indispensable pour que vos changements soient pris en compte.  
- **Lancer le scrapping** : démarre le scraping selon vos paramètres.  
- **Suivi en temps réel** : 4 barres de progression (une par jobboard + une pour le traitement LLM si activé).  
- **Mots-clés** : un mot-clé par ligne.  
- **URLs des sites** : collez l’URL de recherche issue des jobboards après avoir configuré les filtres comme la localisation (des exemples sont fournis).  
- **Jobboards à scrapper** : cochez les plateformes souhaitées.  
- **Options générales** :  
  - Scraping en parallèle (à relancer si certains scrapers échouent).  
  - Activation du LLM.  
- **Paramètres du LLM** :  
  - **Local** : nécessite [Ollama](https://ollama.ai/) avec le modèle *gemma3:12b*.  
  - **ChatGPT** : nécessite une clé API (payant).  
  - **Mistral** : nécessite une clé API (version gratuite limitée).  
- **Générer un score** : attribue un score (0–100) et un commentaire pour chaque offre (le prompt doit garder le format fourni).  
- **Générer un profil personnalisé** : en fournissant un prompt et votre CV, l’application génère un texte accrocheur adapté à chaque offre.  

---

## 📌 Fonctionnalités principales

### 🆕 Nouvelles offres

![Nouvelles offres](imgs%2Fapp_new_job_img.png)

- Pagination (ex. **14/21**)  
- Titre du poste et nom de l’entreprise  
- Lien direct vers l’offre  
- Score (0–100) + commentaire généré par GPT  
- Description de l'offre  
- Boutons disponibles :  
  - **Suivant / Précédent**  
  - **Postuler** → classe l’offre dans *Candidatures en cours*  
  - **Marquer comme lue** → classe l’offre dans *Offres déjà lues*  

---

### 🧹 Offres filtrées par GPT

![app_unintesresting_job_img.png](imgs%2Fapp_unintesresting_job_img.png)

- Contient les offres avec un score **< 50%**  
- Affichage du score et du commentaire GPT  
- Description consultable via un bouton déroulant  
- **Restaurer** → replace l’offre dans *Nouvelles offres*  

---

### 📖 Offres déjà lues

![Offres déjà lues](imgs%2Fapp_already_seen_img.png)

- Liste des offres marquées comme lues  
- Description consultable via un bouton déroulant  
- **Corbeille** → replace l’offre dans *Nouvelles offres*  

---

### ⏳ Candidatures en cours

![Candidatures en cours](imgs%2Fapp_pending_img.png)

- Liste des offres où vous avez postulé  
- **Corbeille** → replace l’offre dans *Offres non lues*  
- **Refusé** → classe l’offre dans *Candidatures refusées*  

---

### ❌ Candidatures refusées

![Candidatures refusées](imgs%2Fapp_refused_img.png)

- Liste des candidatures refusées  
- **Restaurer** → replace l’offre dans *Candidatures en cours*  

---
