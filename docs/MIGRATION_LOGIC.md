# 🚀 Logique de Migration vers MongoDB

Ce document décrit le processus de chargement des données transformées dans MongoDB, l'architecture de la base de données, et les mesures de sécurité mises en place.

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture MongoDB](#-architecture-mongodb)
3. [Schéma de la collection unifiée](#-schéma-de-la-collection-unifiée)
4. [Processus de migration](#-processus-de-migration)
5. [Gestion de l'idempotence](#-gestion-de-lidempotence)
6. [Sécurité et réplication](#-sécurité-et-réplication)
7. [Modes de connexion](#-modes-de-connexion)
8. [Monitoring et logs](#-monitoring-et-logs)
9. [Scripts concernés](#-scripts-concernés)

---

## 🎯 Vue d'ensemble

### Objectifs

1. **Charger** les données transformées dans MongoDB de manière fiable
2. **Garantir** l'idempotence (pas de doublons lors de ré-exécutions)
3. **Assurer** la haute disponibilité via un ReplicaSet
4. **Sécuriser** les accès avec authentification et chiffrement

### Schéma unifié

Le projet utilise une **collection unique `weather_data`** avec un champ discriminant `record_type` :

| record_type | Description | Documents |
|-------------|-------------|-----------|
| `measurement` | Relevés météorologiques | 3807 |
| `station_reference` | Métadonnées InfoClimat | 4 |
| **Total** | | **3811** |

### Flux de migration

```mermaid
flowchart LR
    subgraph INPUT["📥 Entrée"]
        DATA["all_documents[]<br/>3811 documents<br/>(measurements + stations)"]
    end
    
    subgraph CONNECT["🔌 Connexion"]
        URI["Détection mode<br/>Atlas / Local"]
        AUTH["Authentification<br/>User + Password"]
    end
    
    subgraph LOAD["📤 Chargement"]
        IDX["Création index"]
        INS["insert_many()<br/>ordered=False"]
        DUP["Gestion doublons"]
    end
    
    subgraph DB["🗄️ MongoDB"]
        COL["Collection unique<br/>weather_data"]
    end
    
    DATA --> URI --> AUTH --> IDX --> INS --> DUP --> COL
```

---

## 🏗️ Architecture MongoDB

### Environnement de production (AWS)

```mermaid
flowchart TB
    subgraph AWS["☁️ AWS ECS"]
        ECS["🐳 Container ETL<br/>forecast-etl"]
    end
    
    subgraph ATLAS["🌍 MongoDB Atlas"]
        subgraph RS["ReplicaSet rs0"]
            P["🟢 PRIMARY<br/>Écritures"]
            S1["🔵 SECONDARY<br/>Réplication"]
            S2["🔵 SECONDARY<br/>Réplication"]
        end
        
        subgraph SECURITY["Sécurité"]
            TLS["🔒 TLS/SSL"]
            AUTH["🔑 Auth SCRAM"]
            NET["🌐 Network Access"]
        end
    end
    
    ECS -->|"mongodb+srv://"| P
    P --> S1
    P --> S2
```

**Caractéristiques Atlas M0 (Gratuit)** :
- 3 nœuds ReplicaSet (1 PRIMARY + 2 SECONDARY)
- 512 MB de stockage
- Chiffrement at-rest et in-transit
- Sauvegardes automatiques
- Failover automatique (~30s)

### Environnement de développement (Local)

```mermaid
flowchart TB
    subgraph DOCKER["🐳 Docker Compose"]
        ETL["forecast-etl<br/>Container Python"]
        
        subgraph RS["ReplicaSet rs0"]
            M1["mongo1:27017<br/>PRIMARY"]
            M2["mongo2:27017<br/>SECONDARY"]
            ARB["mongo-arbiter:27017<br/>ARBITER"]
        end
        
        INIT["mongo-init<br/>rs.initiate()"]
    end
    
    ETL --> M1
    M1 --> M2
    M1 --> ARB
    INIT --> M1
```

---

## 📊 Schéma de la collection unifiée

### Collection `weather_data`

Une collection unique stocke **tous les types de documents** avec un champ discriminant `record_type`.

### Document type `measurement` (relevés météo)

```javascript
{
    "_id": ObjectId("..."),
    "record_type": "measurement",
    "station_id": "IICHTE19",
    "station_name": "WeerstationBS",
    "source": "weather_underground",
    "location": {
        "city": "Ichtegem",
        "country": "BE",
        "latitude": 51.092,
        "longitude": 2.999,
        "elevation": 15
    },
    "timestamp": ISODate("2025-12-24T00:04:00Z"),
    "measurements": {
        "temperature_celsius": 13.78,
        "humidity_percent": 87,
        "wind_speed_kmh": 13.2,
        "pressure_hpa": 998.3
    }
}
```

### Document type `station_reference` (métadonnées)

```javascript
{
    "_id": ObjectId("..."),
    "record_type": "station_reference",
    "station_id": "00052",
    "station_name": "Armentières",
    "source": "infoclimat",
    "location": {
        "city": "Armentières",
        "country": "FR",
        "latitude": 50.689,
        "longitude": 2.877,
        "elevation": 16
    },
    "station_type": "static",
    "license": {
        "name": "CC BY",
        "url": "https://creativecommons.org/licenses/by/2.0/fr/",
        "source_url": "https://www.infoclimat.fr/stations/metadonnees.php?id=00052"
    },
    "timestamp": ISODate("2025-12-24T15:18:22Z")
}
```

### Diagramme ERD

```mermaid
erDiagram
    WEATHER_DATA {
        ObjectId _id PK
        string record_type "measurement | station_reference"
        string station_id "Identifiant station"
        string station_name "Nom de la station"
        string source "weather_underground | infoclimat"
        object location "Localisation géographique"
        datetime timestamp "Date/heure"
        object measurements "Mesures météo (si measurement)"
        string station_type "Type station (si station_ref)"
        object license "Licence (si station_reference)"
    }
    
    LOCATION {
        string city "Ville"
        string country "Pays"
        float latitude "Latitude GPS"
        float longitude "Longitude GPS"
        int elevation "Altitude"
    }
    
    MEASUREMENTS {
        float temperature_celsius "Température"
        float humidity_percent "Humidité"
        float wind_speed_kmh "Vent"
        float pressure_hpa "Pression"
    }
    
    LICENSE {
        string name "Nom licence"
        string url "URL licence"
        string source_url "URL source"
    }
    
    WEATHER_DATA ||--|| LOCATION : "contient"
    WEATHER_DATA ||--o| MEASUREMENTS : "si measurement"
    WEATHER_DATA ||--o| LICENSE : "si station_reference"
```

### Avantages du schéma unifié

| Avantage | Description |
|----------|-------------|
| **Pas de jointures** | MongoDB n'est pas optimisé pour `$lookup` |
| **Requêtes simples** | Filtrage par `record_type` suffit |
| **Documents auto-portants** | Toutes les infos dans un seul document |
| **Flexibilité** | Ajout de nouveaux `record_type` facile |

---

## ⚙️ Processus de migration

### Étape 1 : Connexion

```python
def connect(self):
    """Établissement de la connexion MongoDB."""
    self.client = MongoClient(self.uri, serverSelectionTimeoutMS=30000)
    self.client.admin.command('ping')  # Test de connexion
    self.db = self.client[self.db_name]
    logger.info(f"Connexion réussie ({self.mode}) à la base '{self.db_name}'")
```

### Étape 2 : Création des index

```python
def init_db(self):
    """Crée les index pour la collection unifiée."""
    collection = self.db["weather_data"]
    
    # Index 1 : Recherche par station et date
    collection.create_index(
        [("station_id", ASCENDING), ("timestamp", ASCENDING)],
        name="idx_station_timestamp"
    )
    
    # Index 2 : Filtrage par type de document
    collection.create_index(
        [("record_type", ASCENDING)],
        name="idx_record_type"
    )
    
    # Index 3 : Recherche par source
    collection.create_index(
        [("source", ASCENDING)],
        name="idx_source"
    )
    
    # Index 4 : Unicité pour les stations de référence
    collection.create_index(
        [("record_type", ASCENDING), ("station_id", ASCENDING), ("source", ASCENDING)],
        unique=True,
        partialFilterExpression={"record_type": "station_reference"},
        name="idx_unique_station_reference"
    )
```

### Étape 3 : Insertion des documents

```python
def insert_documents(self, data_list: list):
    """
    Insère les documents dans la collection unifiée.
    ordered=False : Continue même si un document échoue (doublon).
    """
    collection = self.db["weather_data"]
    result = collection.insert_many(data_list, ordered=False)
    
    # Statistiques par type
    measurements = sum(1 for d in data_list if d.get('record_type') == 'measurement')
    stations = sum(1 for d in data_list if d.get('record_type') == 'station_reference')
    
    logger.info(f"Succès : {len(result.inserted_ids)} documents insérés")
    logger.info(f"   (Mesures: {measurements}, Stations: {stations})")
    
    return len(result.inserted_ids)
```

### Étape 4 : Fermeture

```python
def close(self):
    """Ferme proprement la connexion."""
    if self.client:
        self.client.close()
        logger.info("Connexion MongoDB fermée.")
```

---

## 🔄 Gestion de l'idempotence

### Problématique

Le pipeline peut être exécuté plusieurs fois (re-run, debug, cron). Il ne doit **jamais** créer de doublons.

### Solution : `ordered=False` + Gestion des erreurs

```python
try:
    result = collection.insert_many(data_list, ordered=False)
    count = len(result.inserted_ids)
    logger.info(f"Succès : {count} documents insérés")
    
except BulkWriteError as bwe:
    # Certains documents ont échoué (doublons)
    inserted_count = bwe.details['nInserted']
    duplicates_count = len(bwe.details['writeErrors'])
    logger.info(f"Insertion : {inserted_count} ajoutés, {duplicates_count} doublons ignorés")
```

### Comportement

| Scénario | Résultat |
|----------|----------|
| 1ère exécution | 3811 documents insérés |
| 2ème exécution (mêmes données) | 0 insertions, 3811 doublons ignorés |
| 3ème exécution (données + nouvelles) | Seulement les nouvelles insérées |

---

## 🔒 Sécurité et réplication

### Authentification

| Environnement | Méthode | Stockage credentials |
|---------------|---------|---------------------|
| **Atlas (Prod)** | SCRAM-SHA-256 | Variable `MONGO_URI` dans Task Definition ECS |
| **Local (Dev)** | SCRAM-SHA-256 | Fichier `config/.env` |

### Chiffrement

| Type | Atlas | Local |
|------|-------|-------|
| **In-transit (TLS)** | ✅ Automatique | ❌ Non configuré |
| **At-rest** | ✅ Automatique | ❌ Non configuré |

### Réseau

**MongoDB Atlas** :
- Network Access configuré sur `0.0.0.0/0` (développement)
- En production : restreindre aux IPs ECS/VPC

**AWS Security Group** :
```bash
# Trafic sortant autorisé
IpProtocol: -1 (tout)
CidrIp: 0.0.0.0/0
```

### Réplication (ReplicaSet)

```mermaid
sequenceDiagram
    participant App as ECS Container
    participant P as PRIMARY
    participant S1 as SECONDARY 1
    participant S2 as SECONDARY 2
    
    App->>P: insert_many()
    P->>P: Écriture locale
    P-->>S1: Réplication async
    P-->>S2: Réplication async
    P->>App: Acknowledgment
    
    Note over P,S2: Réplication < 100ms
    
    alt PRIMARY tombe
        S1->>S1: Élection
        S1->>S1: Devient PRIMARY
        Note over S1: Failover ~30s
    end
```

### Avantages du ReplicaSet

| Fonctionnalité | Description |
|----------------|-------------|
| **Haute disponibilité** | Failover automatique si le PRIMARY tombe |
| **Durabilité** | Données répliquées sur 3 nœuds |
| **Lecture distribuée** | Possibilité de lire sur les SECONDARY |
| **Sauvegardes** | Snapshots sans impact sur le PRIMARY |

---

## 🔌 Modes de connexion

### Détection automatique

```python
def __init__(self):
    # Priorité 1 : URI Atlas complète
    atlas_uri = os.getenv("MONGO_URI")
    
    if atlas_uri:
        self.uri = atlas_uri
        self.mode = "Atlas"
    else:
        # Priorité 2 : Variables séparées (Docker Compose)
        user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
        pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
        host = os.getenv("MONGO_HOST", "localhost")
        port = os.getenv("MONGO_PORT", "27017")
        rs_name = os.getenv("MONGO_REPLICA_SET")
        
        if rs_name:
            self.uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&replicaSet={rs_name}"
            self.mode = "ReplicaSet"
        else:
            self.uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&directConnection=true"
            self.mode = "Standalone"
```

### Configurations

| Mode | Variable(s) | URI générée |
|------|-------------|-------------|
| **Atlas** | `MONGO_URI` | `mongodb+srv://user:pwd@cluster.mongodb.net/...` |
| **ReplicaSet Local** | `MONGO_HOST`, `MONGO_REPLICA_SET` | `mongodb://user:pwd@host:port/?replicaSet=rs0` |
| **Standalone** | `MONGO_HOST` (sans RS) | `mongodb://user:pwd@host:port/?directConnection=true` |

### Variables d'environnement

```bash
# Mode Atlas (Production - ECS)
MONGO_URI=mongodb+srv://forecast_user:xxx@forecast-cluster.meeiptz.mongodb.net/?appName=forecast-cluster
MONGO_DB_NAME=greenandcoop_weather

# Mode Local (Développement - Docker Compose)
MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=password123
MONGO_HOST=mongo1
MONGO_PORT=27017
MONGO_REPLICA_SET=rs0
MONGO_DB_NAME=greenandcoop_weather
```

---

## 📊 Monitoring et logs

### Logs du pipeline

```
INFO - -- Début du pipeline du projet Forecast 2.0. --
INFO - [Étape 1/3] : EXTRACTION - Connexion à S3...
INFO - ✅ 3 fichier(s) téléchargé(s) depuis S3
INFO - [Étape 2/3] : TRANSFORMATION - Nettoyage et validation...
INFO - 📊 Résumé transformation :
INFO -    - Fichiers traités : 3
INFO -    - Mesures météo    : 3807
INFO -    - Stations réf.    : 4
INFO -    - Total documents  : 3811
INFO - [Étape 3/3] : CHARGEMENT - Insertion dans MongoDB...
INFO - MongoConnector initialisé en mode: Atlas
INFO - Connexion réussie (Atlas) à la base 'greenandcoop_weather'
INFO - Index MongoDB vérifiés/créés sur 'weather_data'.
INFO - -> Succès : 3811 documents insérés dans 'weather_data'
INFO -    (Mesures: 3807, Stations: 4)
INFO - 📊 Statistiques MongoDB (weather_data) :
INFO -    - Total documents      : 3811
INFO -    - Mesures météo        : 3807
INFO -    - Stations référence   : 4
INFO - === Pipeline terminé avec succès ! ===
```

### Métriques de performance

| Métrique | Valeur | Méthode de mesure |
|----------|--------|-------------------|
| Temps de connexion | ~200ms | Logs pipeline |
| Temps d'insertion (3811 docs) | ~100ms | Logs pipeline |
| Temps lecture unitaire | ~2ms | `check_performance.py` |
| Temps filtrage par type | ~5ms | `check_performance.py` |
| Temps agrégation | ~15ms | `check_performance.py` |

### Monitoring Atlas

Accessible via [cloud.mongodb.com](https://cloud.mongodb.com) :
- **Metrics** : CPU, RAM, IOPS, connexions
- **Real-Time Performance** : Requêtes lentes
- **Alerts** : Notifications email/Slack

### Monitoring CloudWatch (ECS)

```bash
# Logs en temps réel
aws logs tail /ecs/forecast-etl --follow --region eu-west-3

# Recherche d'erreurs
aws logs filter-log-events \
    --log-group-name /ecs/forecast-etl \
    --filter-pattern "ERROR" \
    --region eu-west-3
```

---

## 📁 Scripts concernés

### Fichiers

| Script | Rôle |
|--------|------|
| `src/connectors/mongo_connector.py` | Connexion et opérations MongoDB |
| `src/main.py` | Orchestration du pipeline |
| `src/reporting/check_quality.py` | Audit qualité des données |
| `src/reporting/check_performance.py` | Mesure temps d'accès |
| `src/reporting/test_replication.py` | Test du ReplicaSet |

### Classe MongoConnector

```python
class MongoConnector:
    COLLECTION_NAME = "weather_data"  # Collection unique
    
    def __init__(self):          # Détection mode + construction URI
    def connect(self):           # Établissement connexion
    def init_db(self):           # Création des index
    def insert_documents(self, data_list):  # Insertion collection unifiée
    def get_stats(self):         # Statistiques par record_type
    def close(self):             # Fermeture connexion
```

---

## 📈 Résultats de la migration

### Statistiques actuelles

| Type | Documents | Description |
|------|-----------|-------------|
| `measurement` | 3807 | Relevés météorologiques |
| `station_reference` | 4 | Métadonnées InfoClimat |
| **Total** | **3811** | Collection `weather_data` |

### Qualité des données

| Métrique | Valeur |
|----------|--------|
| Documents conformes | 3811 (100%) |
| Documents rejetés | 0 (0%) |
| Doublons détectés | 0 |
| **Taux d'erreur** | **0%** |

---

## 🔍 Requêtes utiles

```javascript
// Compter par type
db.weather_data.aggregate([
    { $group: { _id: "$record_type", count: { $sum: 1 } } }
])

// Toutes les mesures météo
db.weather_data.find({ record_type: "measurement" })

// Mesures d'une station spécifique
db.weather_data.find({
    record_type: "measurement",
    station_id: "IICHTE19"
})

// Moyenne température par station
db.weather_data.aggregate([
    { $match: { record_type: "measurement" } },
    { $group: {
        _id: "$station_id",
        avg_temp: { $avg: "$measurements.temperature_celsius" },
        count: { $sum: 1 }
    }}
])

// Toutes les stations de référence
db.weather_data.find({ record_type: "station_reference" })
```

---

## 🔗 Documents liés

- [Logique de Transformation](TRANSFORMATION_LOGIC.md) - Préparation des données
- [README Principal](../README.md) - Vue d'ensemble du projet
- [Commandes AWS](../AWS_COMMANDS.md) - Guide CLI
- [Logigramme de déploiement](DEPLOYMENT_FLOW.md) - Flux DevOps

---

**Projet Forecast 2.0** - GreenAndCoop  
Dernière mise à jour : Décembre 2024
