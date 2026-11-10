# JobFinder : recherche d'emploi assistée

Application locale qui **récupère automatiquement les offres de plusieurs sites d'emploi**,
les **évalue avec un LLM** selon vos critères, puis vous aide à **trier les offres et suivre
vos candidatures** (relances, entretiens, statistiques).

Plateformes supportées : **LinkedIn**, **APEC**, **HelloWork**, **France Travail**, **Choisir le Service Public**.

---

## 🚀 Lancer l'application

### Le plus simple : `JobFinder.exe` (Windows)

1. Installez **uv** une seule fois (gestionnaire Python, un seul exécutable) :
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Double-cliquez sur **`JobFinder.exe`** à la racine du projet.

Au premier lancement, uv installe automatiquement la bonne version de Python et toutes les
dépendances (quelques minutes). Les lancements suivants sont immédiats. L'application s'ouvre
dans votre navigateur sur http://localhost:8080. **Fermer la fenêtre noire arrête JobFinder.**

> Variante sans installer uv : copiez `uv.exe` à côté de `JobFinder.exe`.

### En ligne de commande

```bash
uv run python run.py            # avec uv (recommandé)
# ou, dans un environnement Python 3.12+ :
pip install -r requirements.txt
playwright install firefox      # navigateur utilisé pour l'APEC
python run.py
```

### Premier lancement après la version Streamlit

L'ancien fichier `data/job.csv` est importé automatiquement dans la base `data/jobs.db`
(une seule fois, quand la base est vide). Le CSV n'est ni modifié ni supprimé.

---

## 🧭 Utilisation

| Page | Rôle |
|---|---|
| **Tableau de bord** | Offres à traiter, candidatures en cours, relances à faire ; suivi des candidatures (taux d'entretien, refus) ; graphiques : entonnoir, taux de pertinence IA par plateforme, volumes, publications par semaine |
| **Offres** | Onglets *À traiter*, *Écartées*, *Déjà lues* ; filtres (texte, plateforme, ancienneté) ; **seuil de pertinence** réglable en direct |
| **Candidatures** | Onglets *Postulées*, *Entretiens*, *Refusées* ; date de candidature, notes, entretiens réalisés, rappel de relance |
| **Scraping & réglages** | Toute la configuration, lancement d'une mise à jour et suivi en direct (on peut changer de page pendant le scraping) |

**Raccourcis clavier** (listes d'offres) : `←` / `→` naviguer · `L` lue · `P` postuler ·
`R` réhabiliter / remettre à traiter / relancée · `E` entretien réalisé · `X` refusée.
Après une action, l'offre suivante s'affiche à la même place : idéal pour trier à la chaîne.

---

## ⚙️ Fonctionnement d'une mise à jour

1. **Scraping** des plateformes cochées (en parallèle).
2. **Nouvelles offres uniquement** : une offre est déjà connue si son lien ou son empreinte
   (plateforme + titre + entreprise + description) est déjà en base.
3. **Filtres gratuits avant le LLM** : langue de l'offre et pré-filtre par mots (exclus / requis).
   Les offres rejetées sont **conservées avec un score de 0** (onglet *Écartées*) pour ne pas
   revenir comme nouvelles au scraping suivant.
4. **Enregistrement** en base, avant l'évaluation : un plantage du LLM ne fait rien perdre.
5. **Évaluation LLM** : score de 0 à 100 + justification. Les offres dont l'évaluation a
   échoué sont réessayées automatiquement au scraping suivant.

### Règles de tri

- **Statut unique** par offre : *nouvelle → lue* ou *nouvelle → postulée → entretien → refusée*.
- **« Écartée par l'IA »** = offre nouvelle dont le score est inférieur au **seuil**. Le seuil est
  appliqué à l'affichage : le modifier déplace immédiatement les offres entre *À traiter* et
  *Écartées*, sans relancer le LLM. Une offre peut être **réhabilitée** à la main.
- **Doublons probables** : une même offre publiée sur plusieurs sites (même entreprise une fois
  normalisée, titres quasi identiques, publiées à moins de 3 semaines d'écart) est signalée par
  une icône et un encadré indiquant son statut ailleurs (ex : *déjà postulée sur LinkedIn*).
  Rien n'est fusionné automatiquement.
- **Relance** conseillée après N jours sans nouvelle (réglable) ; le bouton *Relancée* note la
  relance dans les notes et remet le compteur à zéro.
- **Entretiens** : chaque entretien réalisé est compté (et conservé après un refus) pour calculer
  le taux d'entretien.

---

## 🔧 Configuration

Tout se règle dans la page **Scraping & réglages**. Les réglages sont enregistrés dans
`config.json` (personnel, non versionné, créé au premier lancement à partir de
`config_default.json`).

- **URL de recherche** : faites une recherche sur le site avec vos filtres (lieu, contrat...),
  puis collez l'URL. Le mot-clé de l'URL est remplacé par chacun de vos mots-clés.
- **Mode des mots-clés** :
  - `one_by_one` : une recherche par mot-clé (plus de volume, plus de bruit) ;
  - `or` : une seule recherche « mot1 OR mot2 » (plus ciblé) ;
  - `all` : une seule recherche avec tous les mots (plus strict).
- **Ancienneté maximale** des offres récupérées (non appliquée au Service Public, dont les
  offres restent ouvertes longtemps).
- **LLM** :
  - **Local** : [Ollama](https://ollama.com/) avec le modèle de votre choix (par défaut `gemma4:26b`) ;
  - **ChatGPT** ou **Mistral** : clé API nécessaire.
- **Critères de recherche** : décrivez uniquement ce que vous voulez, tolérez et refusez.
  Le rôle du LLM, le barème de 0 à 100 et le format de réponse sont ajoutés automatiquement
  (bouton *Voir le prompt complet*). Barème : 0-19 hors cible · 20-49 peu de points communs ·
  50-74 attentes principales remplies · 75-100 excellente correspondance.

### 🔐 Clés API

Les clés ne sont **jamais** dans `config.json` : elles sont dans le fichier **`.env`** à la racine
(exclu de git). Le plus simple est de les saisir dans la page de réglages, qui écrit `.env`.
Sinon, copiez `.env.example` en `.env` :

```bash
GPT_API_KEY=votre-clé-openai
MISTRAL_API_KEY=votre-clé-mistral
```

---

## 💾 Données

| Fichier | Contenu |
|---|---|
| `data/jobs.db` | Base SQLite de toutes les offres (lisible avec pandas : `pd.read_sql("SELECT * FROM jobs", sqlite3.connect("data/jobs.db"))`) |
| `data/backup/` | Copie de la base avant chaque mise à jour |
| `data/jobfinder.log` | Journal de l'application |

Le dossier `data/` n'est pas versionné.

---

## 🗂️ Organisation du code

```
run.py                      point d'entrée (python run.py)
debug_scraper.py            lancer un scraper seul depuis l'IDE (voir « Déboguer un scraper »)
JobFinder.exe               lanceur Windows (source : launcher/JobFinder.cs, compilation : launcher/build.bat)
src/jobfinder/
    config.py               configuration typée et validée (pydantic)
    models.py               statuts, colonnes, règles de pertinence
    storage.py              base SQLite
    migration.py            import unique de l'ancien CSV
    filters.py              filtres de langue et pré-filtre
    llm.py                  évaluation LLM (Ollama / ChatGPT / Mistral) et prompt
    pipeline.py             orchestration d'une mise à jour
    duplicates.py           doublons probables entre plateformes
    scrapers/               un fichier par site + socle commun (base.py)
    ui/                     interface NiceGUI (une page par fichier dans ui/pages/)
tests/                      tests pytest (sans réseau)
```

Le pipeline peut aussi être lancé sans interface : `cd src && python -m jobfinder.pipeline`.

---

## 🐞 Déboguer un scraper

Chaque scraper peut être lancé seul, **sans rien écrire dans la base** :

- **Depuis l'IDE (points d'arrêt)** : ouvrez `debug_scraper.py` à la racine, choisissez la
  plateforme et les réglages en haut du fichier, placez vos points d'arrêt dans
  `src/jobfinder/scrapers/<site>.py`, puis lancez `debug_scraper.py` en mode Debug.
- **En ligne de commande**, depuis `src/` :
  ```bash
  python -m jobfinder.scrapers --list                    # plateformes disponibles
  python -m jobfinder.scrapers ft --max-details 3        # France Travail, 3 fiches seulement
  python -m jobfinder.scrapers hw --keywords "data scientist" --days 3
  ```

Chaque exécution crée `data/debug/<plateforme>_<date-heure>/` avec **chaque page téléchargée**
(`NNN_<code HTTP>_<adresse>.html`, dans l'ordre) et `resultat.csv`. Comparer ces pages avec ce
qu'affiche le navigateur révèle la plupart des pannes : HTML modifié par le site, contenu chargé
en JavaScript (absent des pages téléchargées), blocage antibot… Le journal détaillé indique
chaque requête et pourquoi une offre a été ignorée.

L'APEC tourne dans un processus séparé (navigateur Playwright) ; pour le déboguer :
`python -m jobfinder.scrapers.apec_worker < ../config.json` (depuis `src/`).

---

## 🧪 Tests

```bash
uv run pytest        # ou : pytest
```

Les tests n'accèdent ni au réseau ni au dossier `data/`.

---

## 🛠️ Dépannage

- **Aucune offre récupérée sur un site** : vérifiez que la plateforme est cochée et que l'URL de
  recherche est renseignée ; consultez le journal (page de réglages ou `data/jobfinder.log`).
  Les sites changent régulièrement leur HTML : un scraper peut devoir être adapté
  (`src/jobfinder/scrapers/`).
- **Volume trop faible** : essayez le mode `one_by_one` ; **trop de bruit** : `or` ou `all`.
- **LLM local** : vérifiez qu'Ollama est lancé et que le modèle configuré est installé
  (`ollama list`).
- **Port 8080 déjà utilisé** : une autre instance de JobFinder est probablement ouverte.
