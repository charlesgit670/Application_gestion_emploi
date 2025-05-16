instruction_scoring = """
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
        - supérieur à 50 si une forte part de machine learning 
        et justifie ton choix en énumérant tes arguments en quelques mots tout ça au format json suivant:
        {
        "reponse": "score",
        "justification": "Ta justification"
        }

        Offres : 
        """

instruction_custom_profile = """
Répond par un paragraphe qui est une amélioration de la partie sur l'Objectif professionnel afin qu'elle corresponde
mieux avec l'offre d'emploi. Rédige en français et un maximum de 130 tokens"
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