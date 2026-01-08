# 🌤️ Forecast 2.0 - Pipeline de Données Météorologiques

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green.svg)](https://www.mongodb.com/atlas)
[![AWS](https://img.shields.io/badge/AWS-ECS%20Fargate-orange.svg)](https://aws.amazon.com/ecs/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://www.docker.com/)

## 📋 Table des matières

1. [Contexte du projet](#contexte-du-projet)
2. [Architecture technique](#architecture-technique)
3. [Justifications techniques](#justifications-techniques)
4. [Schéma de la base de données](#schema-de-la-base-de-donnees)
5. [Logigramme du processus ETL](#logigramme-du-processus-etl)
6. [Stack technique](#stack-technique)
7. [Guide de déploiement](#guide-de-deploiement)
8. [Reporting et métriques](#reporting-et-metriques)
9. [Structure du projet](#structure-du-projet)

---

## 🎯 Contexte du projet 

### L'entreprise

**GreenAndCoop** est un fournisseur coopératif français d'électricité d'origine renouvelable dans les Hauts-de-France.

### Le besoin métier

Pour optimiser ses prévisions de demande d'électricité, GreenAndCoop a lancé le projet **Forecast 2.0** avec les objectifs suivants :

| Objectif                    | Description                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------- |
| **Équilibrer le réseau**    | Assurer l'équilibre production/consommation en temps réel pour éviter les pénalités |
| **Optimiser la production** | Planifier l'utilisation des sources renouvelables (solaire, éolien)                 |
| **Gérer les coûts**         | Réduire les achats d'urgence sur le marché de gros                                  |

### Mission Data Engineer

Intégrer de nouvelles sources de données météorologiques (stations semi-professionnelles) dans un pipeline fiable pour alimenter les modèles de prévision des Data Scientists.

### Sources de données

| Source              | Type             | Localisation      | Format        |
| ------------------- | ---------------- | ----------------- | ------------- |
| Weather Underground | Station amateur  | La Madeleine (FR) | Excel → JSONL |
| Weather Underground | Station amateur  | Ichtegem (BE)     | Excel → JSONL |
| InfoClimat          | Réseau open-data | Hauts-de-France   | JSON → JSONL  |

---

## 🏗️ Architecture technique

### Architecture globale

```mermaid
flowchart TB
    subgraph SOURCES["📡 Sources de données"]
        WU1["🌡️ Weather Underground<br/>La Madeleine (FR)"]
        WU2["🌡️ Weather Underground<br/>Ichtegem (BE)"]
        IC["🌐 InfoClimat<br/>Réseau Hauts-de-France"]
    end

    subgraph INGESTION["📥 Ingestion (Airbyte)"]
        AB["⚙️ Airbyte<br/>Connecteurs Excel/JSON"]
    end

    subgraph STOCKAGE_RAW["☁️ Stockage brut (AWS S3)"]
        S3["📦 S3 Bucket<br/>greenandcoop-forecast-raw-data"]
    end

    subgraph ETL["🔄 Pipeline ETL (AWS ECS)"]
        ECS["🐳 ECS Fargate<br/>Container Python"]

        subgraph PROCESSING["Traitement"]
            EX["1️⃣ Extraction<br/>s3_connector.py"]
            TR["2️⃣ Transformation<br/>cleaner.py"]
            VA["3️⃣ Validation<br/>validator.py"]
            LO["4️⃣ Chargement<br/>mongo_connector.py"]
        end
    end

    subgraph STOCKAGE_FINAL["🗄️ Base de données (MongoDB Atlas)"]
        ATLAS["🍃 MongoDB Atlas<br/>ReplicaSet M0"]

        subgraph COLLECTIONS["Collections"]
            MEAS["📊 measurements<br/>3807 documents"]
            STAT["📍 stations<br/>4 documents"]
        end
    end

    subgraph MONITORING["📈 Monitoring (AWS CloudWatch)"]
        CW["📋 CloudWatch Logs<br/>/ecs/forecast-etl"]
    end

    subgraph CONSUMERS["👥 Consommateurs"]
        DS["🧪 Data Scientists<br/>SageMaker"]
    end

    WU1 --> AB
    WU2 --> AB
    IC --> AB
    AB --> S3
    S3 --> ECS
    ECS --> EX --> TR --> VA --> LO
    LO --> ATLAS
    ATLAS --> MEAS
    ATLAS --> STAT
    ECS --> CW
    ATLAS --> DS
```

### Architecture de déploiement AWS

```mermaid
flowchart TB
    subgraph AWS["☁️ AWS Cloud (eu-west-3)"]
        subgraph VPC["🔒 VPC"]
            subgraph SUBNET["Subnet Public"]
                ECS["🐳 ECS Fargate<br/>Task: forecast-etl<br/>0.5 vCPU / 1 GB RAM"]
            end
        end

        subgraph S3_SERVICE["S3"]
            S3["📦 greenandcoop-forecast-raw-data"]
        end

        subgraph ECR_SERVICE["ECR"]
            ECR["🐋 forecast-etl:latest"]
        end

        subgraph CW_SERVICE["CloudWatch"]
            CW["📋 /ecs/forecast-etl"]
        end

        subgraph IAM_SERVICE["IAM"]
            ROLE1["🔑 ecsTaskExecutionRole"]
            ROLE2["🔑 forecast-etl-task-role"]
        end
    end

    subgraph ATLAS["🌍 MongoDB Atlas"]
        CLUSTER["🍃 forecast-cluster<br/>ReplicaSet 3 nœuds<br/>Region: eu-west-3"]
    end

    ECR --> ECS
    ECS --> S3
    ECS --> ATLAS
    ECS --> CW
    ROLE1 --> ECS
    ROLE2 --> ECS
```

### Architecture MongoDB Atlas (ReplicaSet)

```mermaid
flowchart LR
    subgraph ATLAS["MongoDB Atlas - forecast-cluster"]
        subgraph RS["ReplicaSet rs0"]
            P["🟢 PRIMARY<br/>ac-r67aepk-shard-00-00<br/>Lectures/Écritures"]
            S1["🔵 SECONDARY<br/>ac-r67aepk-shard-00-01<br/>Réplication"]
            S2["🔵 SECONDARY<br/>ac-r67aepk-shard-00-02<br/>Réplication"]
        end
    end

    APP["🐳 ECS Container"] --> P
    P -->|"Réplication<br/>asynchrone"| S1
    P -->|"Réplication<br/>asynchrone"| S2

    S1 -.->|"Failover<br/>automatique"| P
    S2 -.->|"Failover<br/>automatique"| P
```

---

## 💡 Justifications techniques

### Pourquoi MongoDB Atlas plutôt que MongoDB sur ECS ?

| Critère                    | MongoDB sur ECS (Self-hosted)                                     | MongoDB Atlas (Managé)                      |
| -------------------------- | ----------------------------------------------------------------- | ------------------------------------------- |
| **ReplicaSet**             | ❌ Très complexe à configurer (IPs dynamiques, Service Discovery) | ✅ Inclus et géré automatiquement           |
| **Haute disponibilité**    | ❌ Configuration manuelle du failover                             | ✅ Failover automatique en ~30s             |
| **Sécurité**               | ⚠️ Gestion manuelle (KeyFile, TLS)                                | ✅ Chiffrement at-rest et in-transit inclus |
| **Sauvegardes**            | ❌ À implémenter (scripts, S3)                                    | ✅ Snapshots automatiques inclus            |
| **Monitoring**             | ❌ À configurer (Prometheus, Grafana)                             | ✅ Dashboard intégré avec alertes           |
| **Coût (petit volume)**    | ~$30-50/mois (3 instances EC2)                                    | ✅ **Gratuit** (M0 Free Tier)               |
| **Maintenance**            | ❌ Patches, upgrades manuels                                      | ✅ Automatique                              |
| **Temps de mise en place** | ~2-3 jours                                                        | ~10 minutes                                 |

**Conclusion** : Pour un projet d'étude avec un faible volume de données (~1.7 Mo), MongoDB Atlas M0 offre toutes les fonctionnalités d'un ReplicaSet de production **gratuitement**, sans la complexité opérationnelle.

### Pourquoi ECS Fargate ?

| Critère                 | EC2                              | ECS Fargate                       |
| ----------------------- | -------------------------------- | --------------------------------- |
| **Gestion serveurs**    | ❌ Provisioning, patches         | ✅ Serverless                     |
| **Scaling**             | ⚠️ Manuel ou Auto Scaling Groups | ✅ Automatique                    |
| **Coût (job ponctuel)** | ~$0.50/heure (instance allumée)  | ✅ ~$0.01/exécution (pay-per-use) |
| **Complexité**          | ⚠️ AMI, Security Groups, etc.    | ✅ Juste une Task Definition      |

**Conclusion** : Pour un job ETL ponctuel qui s'exécute en ~1 seconde, Fargate est idéal (on ne paie que le temps d'exécution).

### Pourquoi Airbyte pour l'ingestion ?

| Critère            | Scripts manuels   | Airbyte                      |
| ------------------ | ----------------- | ---------------------------- |
| **Connecteurs**    | ❌ À développer   | ✅ 300+ connecteurs prêts    |
| **Transformation** | ❌ Code custom    | ✅ Normalisation automatique |
| **Monitoring**     | ❌ À implémenter  | ✅ UI avec historique        |
| **Orchestration**  | ❌ Cron + scripts | ✅ Scheduling intégré        |

---

## 🗄️ Schéma de la base de données

### Vue d'ensemble

```mermaid
erDiagram
    MEASUREMENTS {
        ObjectId _id PK
        string station_id FK
        string station_name
        datetime timestamp
        float temperature_celsius
        float humidity_percent
        float wind_speed_kmh
        float pressure_hpa
        float latitude
        float longitude
    }

    STATIONS {
        ObjectId _id PK
        string station_id UK
        string station_name
        float latitude
        float longitude
        int elevation
        string type
        object license
        datetime timestamp
    }

    STATIONS ||--o{ MEASUREMENTS : "1:N"
```

### Collection `measurements` (3807 documents)

Stocke les relevés météorologiques des stations.

```json
{
  "_id": "ObjectId('694c043e8a0415f138a07009')",
  "station_id": "IICHTE19",
  "station_name": "WeerstationBS",
  "timestamp": "2025-12-24T00:04:00.000+00:00",
  "temperature_celsius": 13.78,
  "humidity_percent": 87,
  "wind_speed_kmh": 13.2,
  "pressure_hpa": 998.3,
  "latitude": 51.092,
  "longitude": 2.999
}
```

| Champ                 | Type     | Description                      | Validation |
| --------------------- | -------- | -------------------------------- | ---------- |
| `station_id`          | String   | Identifiant unique de la station | Requis     |
| `station_name`        | String   | Nom de la station                | Optionnel  |
| `timestamp`           | DateTime | Date/heure du relevé             | Requis     |
| `temperature_celsius` | Float    | Température en °C                | -60 à +60  |
| `humidity_percent`    | Float    | Humidité relative                | 0 à 100    |
| `wind_speed_kmh`      | Float    | Vitesse du vent                  | ≥ 0        |
| `pressure_hpa`        | Float    | Pression atmosphérique           | 800 à 1200 |
| `latitude`            | Float    | Latitude GPS                     | Optionnel  |
| `longitude`           | Float    | Longitude GPS                    | Optionnel  |

### Collection `stations` (4 documents)

Stocke les métadonnées des stations météorologiques.

```json
{
  "_id": "ObjectId('694c043e8a0415f138a07ee8')",
  "station_id": "00052",
  "station_name": "Armentières",
  "latitude": 50.689,
  "longitude": 2.877,
  "elevation": 16,
  "type": "static",
  "license": { "name": "ODbL", "url": "..." },
  "timestamp": "2025-12-24T15:18:22.043+00:00"
}
```

### Index créés

```javascript
// Collection measurements - Index composé pour requêtes temporelles par station
db.measurements.createIndex(
  { station_id: 1, timestamp: 1 },
  { name: "unique_station_timestamp" }
);

// Collection stations - Index unique sur l'identifiant
db.stations.createIndex(
  { station_id: 1 },
  { unique: true, name: "unique_station_id" }
);
```

---

## 📊 Logigramme du processus ETL

### Processus global

```mermaid
flowchart TD
    START([🚀 DÉBUT]) --> INIT["Initialisation<br/>Chargement .env"]

    INIT --> CHECK_ENV{{"Variables<br/>d'environnement<br/>valides ?"}}
    CHECK_ENV -->|Non| ERROR_ENV[/"❌ ERREUR :<br/>Configuration manquante"/]
    ERROR_ENV --> END_ERROR([🔴 FIN - Échec])

    CHECK_ENV -->|Oui| STEP1["📥 ÉTAPE 1 : EXTRACTION<br/>Connexion à S3"]

    STEP1 --> S3_CONNECT{{"Connexion S3<br/>réussie ?"}}
    S3_CONNECT -->|Non| ERROR_S3[/"❌ ERREUR :<br/>Accès S3 refusé"/]
    ERROR_S3 --> END_ERROR

    S3_CONNECT -->|Oui| DOWNLOAD["Téléchargement des fichiers<br/>vers data/downloaded/"]

    DOWNLOAD --> FILES_EXIST{{"Fichiers<br/>trouvés ?"}}
    FILES_EXIST -->|Non| WARN_EMPTY[/"⚠️ AVERTISSEMENT :<br/>Bucket vide"/]
    WARN_EMPTY --> END_WARN([🟡 FIN - Aucune donnée])

    FILES_EXIST -->|Oui| STEP2["🔄 ÉTAPE 2 : TRANSFORMATION"]

    STEP2 --> LOOP_START{{"Pour chaque<br/>fichier"}}

    LOOP_START --> DETECT_TYPE{{"Type de<br/>fichier ?"}}

    DETECT_TYPE -->|"station_*.jsonl"| TRANSFORM_WEATHER["Transformation météo<br/>• Mapping colonnes<br/>• °F → °C<br/>• mph → km/h<br/>• inHg → hPa"]

    DETECT_TYPE -->|"*info_climat*"| TRANSFORM_STATION["Transformation stations<br/>• Extraction métadonnées<br/>• Normalisation coords"]

    TRANSFORM_WEATHER --> VALIDATE["🔍 Validation Pydantic<br/>• Limites température<br/>• Limites humidité<br/>• Types de données"]

    TRANSFORM_STATION --> STORE_STATIONS[("💾 Stockage temporaire<br/>stations_data[]")]

    VALIDATE --> VALID_CHECK{{"Données<br/>valides ?"}}
    VALID_CHECK -->|Oui| STORE_MEASURES[("💾 Stockage temporaire<br/>measurements_data[]")]
    VALID_CHECK -->|Non| LOG_REJECT[/"📝 LOG :<br/>Motif de rejet"/]
    LOG_REJECT --> STORE_MEASURES

    STORE_MEASURES --> LOOP_END{{"Autres<br/>fichiers ?"}}
    STORE_STATIONS --> LOOP_END
    LOOP_END -->|Oui| LOOP_START

    LOOP_END -->|Non| STEP3["📤 ÉTAPE 3 : CHARGEMENT"]

    STEP3 --> MONGO_CONNECT["Connexion MongoDB Atlas"]

    MONGO_CONNECT --> MONGO_OK{{"Connexion<br/>réussie ?"}}
    MONGO_OK -->|Non| ERROR_MONGO[/"❌ ERREUR :<br/>Timeout MongoDB"/]
    ERROR_MONGO --> END_ERROR

    MONGO_OK -->|Oui| CREATE_INDEX["Création/Vérification<br/>des index"]

    CREATE_INDEX --> INSERT_MEAS["Insertion measurements<br/>ordered=False<br/>(gestion doublons)"]

    INSERT_MEAS --> INSERT_STAT["Insertion stations<br/>ordered=False<br/>(gestion doublons)"]

    INSERT_STAT --> CLOSE_CONN["Fermeture connexion"]

    CLOSE_CONN --> LOG_SUCCESS[/"📝 LOG :<br/>Pipeline terminé avec succès"/]

    LOG_SUCCESS --> END_SUCCESS([🟢 FIN - Succès])
```

### Légende des symboles

| Symbole               | Signification                   |
| --------------------- | ------------------------------- |
| ⬭ (Rectangle arrondi) | Début / Fin                     |
| ▭ (Rectangle)         | Processus / Action              |
| ◇ (Losange)           | Décision / Condition            |
| ▱ (Parallélogramme)   | Entrée / Sortie (logs, erreurs) |
| ⌓ (Cylindre)          | Stockage de données             |

---

## 🛠️ Stack technique

### Langages et frameworks

| Outil    | Version | Usage                    |
| -------- | ------- | ------------------------ |
| Python   | 3.12    | Langage principal        |
| Pydantic | 2.x     | Validation des données   |
| PyMongo  | 4.x     | Driver MongoDB           |
| Boto3    | 1.x     | SDK AWS (S3)             |
| Pandas   | 2.x     | Manipulation des données |

### Infrastructure

| Service             | Usage                   | Justification                      |
| ------------------- | ----------------------- | ---------------------------------- |
| **AWS S3**          | Stockage données brutes | Scalable, durable, intégré Airbyte |
| **AWS ECS Fargate** | Exécution du pipeline   | Serverless, pay-per-use            |
| **AWS ECR**         | Registry Docker         | Intégré ECS, sécurisé              |
| **AWS CloudWatch**  | Logs et monitoring      | Natif AWS, temps réel              |
| **MongoDB Atlas**   | Base de données         | ReplicaSet gratuit, managé         |
| **Airbyte**         | Ingestion des données   | Connecteurs prêts à l'emploi       |

### Outils de développement

| Outil                   | Usage                         |
| ----------------------- | ----------------------------- |
| Docker / Docker Compose | Conteneurisation et dev local |
| pytest                  | Tests unitaires               |
| Git                     | Versioning                    |

---

## 🚀 Guide de déploiement

### Prérequis

- Compte AWS avec droits ECS, ECR, S3, IAM, CloudWatch
- Compte MongoDB Atlas (gratuit)
- Docker Desktop installé
- AWS CLI configuré (`aws configure`)
- Python 3.12+

### Étape 1 : Configuration MongoDB Atlas

1. Créer un cluster M0 (gratuit) sur [MongoDB Atlas](https://cloud.mongodb.com)
2. Région : `AWS eu-west-3` (Paris)
3. Créer un utilisateur `forecast_user` avec droits Read/Write
4. Network Access : Ajouter `0.0.0.0/0` (ou les IPs ECS)
5. Récupérer l'URI de connexion

### Étape 2 : Préparation de l'image Docker

```bash
# Build de l'image
docker build --platform linux/amd64 -t forecast-etl .

# Tag pour ECR
docker tag forecast-etl:latest <ACCOUNT_ID>.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest

# Login ECR
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.eu-west-3.amazonaws.com

# Push
docker push <ACCOUNT_ID>.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest
```

### Étape 3 : Déploiement ECS

```bash
# Créer les rôles IAM (si nécessaire)
aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://trust-policy.json
aws iam create-role --role-name forecast-etl-task-role --assume-role-policy-document file://trust-policy.json

# Créer le Log Group
aws logs create-log-group --log-group-name /ecs/forecast-etl --region eu-west-3

# Enregistrer la Task Definition
aws ecs register-task-definition --cli-input-json file://task-definition.json --region eu-west-3

# Exécuter la Task
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
    --region eu-west-3
```

### Étape 4 : Vérification

```bash
# Suivre les logs en temps réel
aws logs tail /ecs/forecast-etl --follow --region eu-west-3
```

Résultat attendu :

```
INFO - -- Début du pipeline du projet Forecast 2.0. --
INFO - [Etape 1/3] : CONNEXION A S3 et RECUPERATION DES FICHIERS...
INFO - Succès : 3 fichiers telechargés depuis S3
INFO - [Etape 2/3] : NETTOYAGE ET TRANSFORMATION DES DONNEES...
INFO - Total prêt : 3811 documents.
INFO - [Etape 3/3] : INSERTION DES DONNES DANS MONGODB...
INFO - MongoConnector initialisé en mode: Atlas
INFO - Connexion réussie (Atlas) à la base 'greenandcoop_weather'
INFO - -> Succès : 3807 documents insérés dans 'measurements'.
INFO - -> Succès : 4 documents insérés dans 'stations'.
INFO - === Pipeline terminé avec succès ! ===
```

---

## 📈 Reporting et métriques

### Temps d'exécution du pipeline

| Étape              | Durée     | Performance  |
| ------------------ | --------- | ------------ |
| Extraction S3      | ~0.6s     | ✅ Excellent |
| Transformation     | ~0.3s     | ✅ Excellent |
| Connexion MongoDB  | ~0.2s     | ✅ Excellent |
| Insertion données  | ~0.1s     | ✅ Excellent |
| **Total pipeline** | **~1.2s** | ✅ Excellent |

### Qualité des données

| Métrique          | Valeur | Seuil | Statut |
| ----------------- | ------ | ----- | ------ |
| Documents traités | 3811   | -     | -      |
| Documents valides | 3811   | -     | -      |
| Documents rejetés | 0      | <1%   | ✅     |
| **Taux d'erreur** | **0%** | <1%   | ✅     |

### Temps d'accessibilité (MongoDB Atlas)

| Requête                           | Temps | Seuil  | Statut |
| --------------------------------- | ----- | ------ | ------ |
| Lecture unitaire (dernier relevé) | ~2ms  | <50ms  | ✅     |
| Agrégation (moyenne température)  | ~15ms | <100ms | ✅     |

### Scripts de reporting

```bash
# Mesurer la performance (depuis le conteneur ou en local)
python -m src.reporting.check_performance

# Vérifier la qualité des données
python -m src.reporting.check_quality

# Tester la réplication (environnement local uniquement)
python -m src.reporting.test_replication
```

---

## 📁 Structure du projet

```
greenandcoop-forecast/
│
├── 📄 README.md                    # Ce fichier
├── 📄 Dockerfile                   # Image Docker du pipeline
├── 📄 docker-compose.yml           # Environnement local (ReplicaSet)
├── 📄 requirements.txt             # Dépendances Python
│
├── 📁 config/
│   └── 📄 .env                     # Variables d'environnement
│
├── 📁 src/
│   ├── 📄 __init__.py
│   ├── 📄 main.py                  # Point d'entrée du pipeline
│   │
│   ├── 📁 connectors/
│   │   ├── 📄 s3_connector.py      # Connexion AWS S3
│   │   └── 📄 mongo_connector.py   # Connexion MongoDB (Atlas/Local)
│   │
│   ├── 📁 processing/
│   │   ├── 📄 cleaner.py           # Transformation des données
│   │   └── 📄 validator.py         # Validation Pydantic
│   │
│   └── 📁 reporting/
│       ├── 📄 check_performance.py # Mesure temps d'accès
│       ├── 📄 check_quality.py     # Audit qualité données
│       └── 📄 test_replication.py  # Test réplication (local)
│
├── 📁 tests/
│   └── 📄 test_quality.py          # Tests unitaires pytest
│
├── 📁 docs/
│   ├── 📄 TRANSFORMATION_LOGIC.md  # Logique de transformation
│   ├── 📄 MIGRATION_LOGIC.md       # Logique de migration
│   └── 📁 diagrams/                # Diagrammes exportés
│
├── 📁 ecs-deployment/              # Fichiers déploiement AWS
│   ├── 📄 task-definition.json
│   ├── 📄 trust-policy.json
│   └── 📄 s3-access-policy.json
│
└── 📁 logs/                        # Logs locaux
    └── 📄 pipeline.log
```

---

## 📞 Contact

**Projet** : Forecast 2.0 - GreenAndCoop  
**Data Engineer** : Abd Selam M'BODJ  
**Date** : Décembre 2025

---

## 📚 Documentation complémentaire

- [Logique de transformation](docs/TRANSFORMATION_LOGIC.md)
- [Logique de migration](docs/MIGRATION_LOGIC.md)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
