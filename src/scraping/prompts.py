instruction_scoring = """
Tu es un assistant spécialisé dans l’analyse d’offres d’emploi. 
Ton objectif est d’évaluer si une offre correspond **exactement** à ma recherche d’un CDI en Data Science avec **implémentation technique réelle de modèles ML/statistiques**.

Ce que je recherche absolument :
- CDI
- Poste technique : Data Scientist, Machine Learning Engineer, AI Engineer, etc.
- Développement et implémentation **réelle et autonome** de modèles de machine learning et statistiques (ex : régression linéaire, détection d’anomalies, clustering, réseaux de neurones, etc.)
- Analyse et interprétation des résultats des modèles
- Secteur à fort impact comme l'industriel (ex : énergie, écologie)
- Utilisation de Python pour le développement des modèles


Ce que tu tolères mais **ne compte jamais pour un score ≥50** :
- Intégration, utilisation ou déploiement de services ML/IA existants (Azure AI, APIs LLM, etc.)
- Préparation et nettoyage des données
- Industrialisation ou mise en production de modèles
- Présentation ou reporting des résultats
- Veille technologique ou proposition d’innovations
- Développement d’interface simple type Streamlit
- Connaissance conceptuelle de l’IA/ML sans implémentation technique directe


Ce que tu dois absolument éliminer (score <50) :
- Stage, alternance ou apprentissage
- Poste orienté Data Analyst ou Data Engineer
- Product Owner, gestion de projet, chef de projet, management sans implémentation technique
- Secteurs non industriels ou hors impact énergétique/écologique (ex : banque, assurance, retail, e-commerce, consulting, santé, pharmaceutique)
- Développement front-end (React, Angular, HTML, CSS, JavaScript, TypeScript)

Pour chaque offre, réponds avec un score d’intérêt entre 0 et 100 :
- 0 à 49 : l’offre **ne demande pas d’implémentation technique réelle** de modèles ML/statistiques à partir de zéro
- 50 à 100 : l’offre **demande réellement de développer et implémenter** des modèles ML/statistiques à partir de zéro

Format de réponse (obligatoire, JSON strict) :
{
  "reponse": SCORE_ENTIER,
  "justification": "Arguments courts séparés par des points-virgules"
}

Offres :
"""

instruction_custom_profile = """
Répond par un paragraphe qui est une amélioration de la partie sur l'Objectif professionnel afin qu'elle corresponde
mieux avec l'offre d'emploi. Rédige en français et un maximum de 130 tokens
"""

my_resume = """
# Charles LOGEAIS

## Objectif professionnel

**Data Scientist**  
Passionné par le Machine Learning et la compréhension des algorithmes, je suis actuellement à la recherche d’un poste en tant que Data Scientist. Je souhaite apporter ma contribution aux projets innovants exploitant l'intelligence artificielle au sein des entreprises.

---

## Expériences professionnelles

### Alternance Data Scientist – MeilleurTaux, Paris (2022 - 2024)
- Développement d’un outil d’analyse des mises à jour tarifaires dans les PDF de tarifs bancaires
- Mise en place d’un score de défaut de paiement à partir des historiques bancaires
- Classification de documents bancaires selon divers critères (civilité, banque…)
- Développement d’un outil interactif de recherche basé sur les LLM (RAG)

**Outils :** Python, Scikit-learn, TensorFlow, Numpy, Pandas, Matplotlib, Streamlit, PyMuPDF, Selenium, GitLab/GitHub, GCP, Docker, PyCharm

---

### Ingénieur d’études et développement – Groupe HN (CACIB), Guyancourt (2020 - 2022)
- Développement d'une application d'automatisation de la supply chain en Java
- Implémentation technique des besoins fonctionnels
- Analyse et correction des incidents, déploiement et suivi des livraisons

**Outils :** Java, SQL, Spring, Hibernate, Cucumber, Microsoft SQL, base H2, Intellij, Eclipse, GitLab, Méthode Agile

---

### Ingénieur d’études et développement – ADAMING (AIFE), Noisy-le-Grand (2019 - 5 mois)
- Analyse d’incidents (logs, supervision, BDD)
- Maintien en Condition Opérationnelle
- Évolution de scripts Shell, tests et livraisons

**Outils :** Shell, SQL, Linux, Virtual Machine, Oracle SQL Developer, logiciels AXWAY

---

## Diplômes et Formations

- **Mastère 2 : Intelligence Artificielle et Big Data**  
  École Supérieure de Génie Informatique, Paris (2022 - 2024)  
  *Mention bien – 2e sur 28*

- **Master 2 : Sciences de la Fusion et des Plasmas**  
  Université de Lorraine, Nancy (2017 - 2018)  
  *Mention bien*

- **Master 2 : Mécanique des Fluides et Physique Non-linéaire**  
  Aix-Marseille Université, Marseille (2015 - 2016)

- **Licence : Physique**  
  Université Nice Sophia-Antipolis, Nice (2011 - 2014)

---

## Compétences

### Langages
- Python, SQL, Java

### Frameworks / Bibliothèques
- TensorFlow, PyTorch, Scikit-learn, Numpy, Pandas, Matplotlib, Streamlit, PyMuPDF, Selenium

### Cloud
- GCP (déploiement d’applications, outils IA)

### Outils
- GitLab/GitHub, Docker

### IDE
- PyCharm, Anaconda, Jupyter Notebook, Intellij

### Machine Learning
- Apprentissage supervisé et non supervisé
- Traitement du langage naturel (NLP)
- Séries temporelles
- Apprentissage par renforcement
- Vision par ordinateur

---

## Certifications

- [Deep Learning – Andrew Ng (Coursera)](https://www.coursera.org/account/accomplishments/specialization/TJ72UUCSJBSQ)
- [Machine Learning – Andrew Ng (Coursera)](https://www.coursera.org/account/accomplishments/verify/TNARYMCLTZVA)
- [Introduction aux statistiques – Guenther Walther (Coursera)](https://www.coursera.org/learn/stanford-statistics)

---

## Langues

- Français : Langue maternelle  
- Anglais : TOEIC 825

---

## Centres d’intérêt

- Pratique du badminton en compétition  
- Curiosité scientifique (chaînes de vulgarisation scientifique et informatique)

"""