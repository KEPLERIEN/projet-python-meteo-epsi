# Dashboard Météo & Qualité de l'Air

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-interactif-3F4F75?logo=plotly&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-analyse%20de%20donn%C3%A9es-150458?logo=pandas&logoColor=white)
![Tests](https://img.shields.io/badge/tests-unittest%20%7C%20pytest-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

> Application Python de **surveillance météo et de la qualité de l'air en temps réel**, avec dashboard
> interactif, indicateurs de confort, système d'alertes et mise en cache locale.

**Projet EPSI — 3ᵉ année du cycle Ingénieur (FISE / FISA)** — réalisé en trinôme.

---

## Sommaire

- [Contexte & objectifs](#contexte--objectifs)
- [Fonctionnalités](#fonctionnalités)
- [Architecture du projet](#architecture-du-projet)
- [Stack technique](#stack-technique)
- [Démarrage rapide](#démarrage-rapide)
- [Utilisation du dashboard](#utilisation-du-dashboard)
- [Seuils d'alerte (OMS)](#seuils-dalerte-oms)
- [Tests](#tests)
- [APIs de données](#apis-de-données)
- [Répartition de l'équipe](#répartition-de-léquipe)
- [Feuille de route](#feuille-de-route)
- [Licence](#licence)

---

## Contexte & objectifs

Dans le cadre des enjeux de transition écologique et de santé publique, cette application permet de :

1. **Collecter** automatiquement des données météo et environnementales via des APIs REST publiques.
2. **Traiter**, nettoyer et enrichir ces données avec Pandas.
3. **Restituer** l'information dans un dashboard interactif : graphiques, cartes KPI, carte géographique et alertes.

Le projet suit une architecture modulaire inspirée du pattern **MVC** : la récupération des données,
le traitement métier et la couche d'affichage sont strictement séparés.

---

## Fonctionnalités

### MVP — obligatoire

| Domaine | Fonctionnalité | Statut |
| --- | --- | :---: |
| Ingestion | Récupération multi-villes (Paris, Lyon, Marseille, Rennes, Grenoble) | Oui |
| Ingestion | Données météo : température, humidité, pression, vent | Oui |
| Ingestion | Données qualité de l'air : AQI + PM2.5, PM10, NO2, O3, CO, SO2 | Oui |
| Ingestion | Cache local **SQLite** avec TTL de 30 minutes | Oui |
| Traitement | Indice global de santé / confort (score composite 0–100) | Oui |
| Traitement | Détection des dépassements de seuils (normes OMS) | Oui |
| Interface | Dashboard **Streamlit** avec cartes KPI | Oui |
| Interface | Graphiques temporels interactifs (**Plotly**) | Oui |
| Interface | Carte géographique interactive (Plotly Mapbox) | Oui |

### Bonus

| Fonctionnalité | Statut |
| --- | :---: |
| Mode Déconnecté / Simulation (données mockées en cas de coupure réseau) | Oui |
| Prédictions par Machine Learning (H+24) | À venir |
| Export de rapports (PDF / CSV) | À venir |
| Conteneurisation Docker | À venir |

---

## Architecture du projet

```text
projet-python-meteo-epsi/
├── data/                         # Cache local — base SQLite (data/data_cache.db)
├── src/
│   ├── __init__.py
│   ├── api_client.py             # Requêtes API + gestion du cache SQLite (TTL)
│   ├── data_processing.py        # Nettoyage, fusion et calculs Pandas
│   ├── alerts.py                 # Seuils OMS + moteur de règles d'alerte
│   └── dashboard.py              # Application UI (Streamlit)
├── tests/
│   ├── test_api.py               # Tests du client API
│   └── test_processing.py        # Tests du traitement & des alertes
├── dashboard_meteo_qualite_air_boilerplate.py   # Fichier sujet d'origine
├── requirements.txt              # Dépendances du projet
├── LICENSE
└── README.md
```

### Rôle des modules

- **`api_client.py`** — classe `WeatherAPIClient` : appels HTTP vers Open-Meteo, gestion du cache
  SQLite (`data/data_cache.db`) avec expiration à 30 minutes, et génération de données simulées en
  cas d'échec réseau.
- **`data_processing.py`** — classe `DataProcessor` : transformation des réponses JSON en
  `DataFrame`, fusion météo / qualité de l'air et calcul du score de confort.
- **`alerts.py`** — `THRESHOLDS` (seuils OMS) et fonction `detect_alerts()` : analyse du dernier
  point de mesure et génération des alertes.
- **`dashboard.py`** — fonction `render_dashboard()` : construction de l'interface Streamlit
  (filtres, KPI, graphiques, carte).

---

## Stack technique

- **Langage** : Python 3.10+
- **Traitement de données** : Pandas, NumPy
- **Visualisation** : Plotly (Express), Streamlit
- **Requêtes HTTP** : Requests
- **Persistance** : SQLite (module `sqlite3`, sans dépendance externe)
- **Tests** : unittest / pytest

Dépendances (voir [`requirements.txt`](requirements.txt)) : `requests`, `pandas`, `numpy`, `plotly`, `streamlit`.

---

## Démarrage rapide

### Prérequis

- Python 3.10 ou supérieur
- `pip`

### Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/<votre-compte>/projet-python-meteo-epsi.git
cd projet-python-meteo-epsi

# 2. (Recommandé) Créer un environnement virtuel
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

### Lancement de l'application

```bash
streamlit run src/dashboard.py
```

Le dashboard s'ouvre automatiquement dans le navigateur à l'adresse `http://localhost:8501`.

> Aucune clé d'API n'est requise : les APIs Open-Meteo sont gratuites et sans authentification.
> Si le réseau est indisponible, activez le **Mode Déconnecté** dans la barre latérale pour utiliser
> le jeu de données simulé.

---

## Utilisation du dashboard

La barre latérale (**Configuration**) permet de :

- **Sélectionner une ville** parmi Paris, Lyon, Marseille, Rennes et Grenoble ;
- Activer le **Mode Déconnecté / Data Mocked** (données simulées, sans appel réseau).

Le panneau principal affiche :

1. **Zone d'alertes** — bannière rouge (danger) ou orange (vigilance) en cas de dépassement de seuil.
2. **Cartes KPI** — Température, Humidité, Indice AQI (US), PM 2.5, Score de confort (0–100).
3. **Trois onglets** :
   - *Évolution Météo* — série temporelle température / humidité ;
   - *Qualité de l'Air* — concentrations des polluants sur les 24 dernières heures ;
   - *Carte Interactive* — localisation de la station de mesure.

---

## Seuils d'alerte (OMS)

Définis dans [`src/alerts.py`](src/alerts.py) :

| Indicateur | Vigilance | Danger | Unité |
| --- | :---: | :---: | :---: |
| PM 2.5 | 15.0 | 25.0 | µg/m³ |
| PM 10 | 45.0 | 50.0 | µg/m³ |
| NO2 | 25.0 | 50.0 | µg/m³ |
| Température max | 33.0 | 38.0 | °C |

---

## Tests

Les tests unitaires vérifient le calcul du score de confort et la détection des alertes.

```bash
# Avec pytest (recommandé)
pip install pytest
pytest tests/ -v

# Alternative sans dépendance externe : unittest
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## APIs de données

| API | Usage | Authentification |
| --- | --- | --- |
| [Open-Meteo](https://open-meteo.com/) | Météo (température, humidité, pression, vent) | Aucune |
| [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) | Qualité de l'air (PM2.5, PM10, NO2, O3, CO, SO2, AQI) | Aucune |

---

## Répartition de l'équipe

| Membre | Rôle | Modules |
| --- | --- | --- |
| Étudiant A | Ingénieur Données & API Integration | `api_client.py` |
| Étudiant B | Data Analyst & Logique Métier | `data_processing.py`, `alerts.py`, tests |
| Étudiant C | Lead UI / UX & Visualisation | `dashboard.py` |

---

## Feuille de route

- [ ] Prédiction de la température / du PM 2.5 à **H+24** (scikit-learn : régression linéaire).
- [ ] Export automatique de synthèses au format **PDF / CSV**.
- [ ] **Conteneurisation Docker** (`Dockerfile` + `docker-compose.yml`).
- [ ] Positionnement des clés d'API dans un fichier `.env` (si une API le nécessite).

---

## Licence

Distribué sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.
