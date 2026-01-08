# 🔄 Guide de Migration vers le Schéma Unifié

Ce document décrit les étapes pour migrer vers la collection unique `weather_data`.

---

## 📊 Changements effectués


### Après (1 collection unifiée)

```
weather_data (3811 docs)
├── record_type: "measurement"        →  Relevés météo (3807)
└── record_type: "station_reference"  →  Métadonnées (4)
```

---

## 📁 Fichiers modifiés

| Fichier | Modification |
|---------|--------------|
| `src/processing/cleaner.py` | Nouveau format de sortie unifié |
| `src/processing/validator.py` | Nouveaux modèles Pydantic |
| `src/connectors/mongo_connector.py` | Collection unique `weather_data` |
| `src/main.py` | Logique simplifiée |
| `src/reporting/check_quality.py` | Requêtes adaptées |
| `src/reporting/check_performance.py` | Requêtes adaptées |
| `tests/test_quality.py` | Tests mis à jour |

---

## 🚀 Étapes de redéploiement

### Étape 1 : Remplacer les fichiers localement

```bash
# Copier les nouveaux fichiers dans ton projet
cp cleaner.py /chemin/vers/greenandcoop-forecast/src/processing/
cp validator.py /chemin/vers/greenandcoop-forecast/src/processing/
cp mongo_connector.py /chemin/vers/greenandcoop-forecast/src/connectors/
cp main.py /chemin/vers/greenandcoop-forecast/src/
cp check_quality.py /chemin/vers/greenandcoop-forecast/src/reporting/
cp check_performance.py /chemin/vers/greenandcoop-forecast/src/reporting/
cp test_quality.py /chemin/vers/greenandcoop-forecast/tests/
```

### Étape 2 : Tester en local (optionnel)

```bash
cd greenandcoop-forecast

# Lancer les tests unitaires
pytest tests/test_quality.py -v

# Tester avec Docker Compose
docker-compose up --build
```

### Étape 3 : Nettoyer MongoDB Atlas (anciennes collections)

Connecte-toi à MongoDB Atlas et supprime les anciennes collections :

**Via l'interface web :**
1. Va sur [cloud.mongodb.com](https://cloud.mongodb.com)
2. Clique sur ton cluster → **Browse Collections**
3. Supprime les collections `measurements` et `stations`

**Ou via mongosh :**
```javascript
use greenandcoop_weather
db.measurements.drop()
db.stations.drop()
```

### Étape 4 : Rebuild et Push l'image Docker

```bash
# Build
docker build --platform linux/amd64 -t forecast-etl .

# Tag
docker tag forecast-etl:latest 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest

# Login ECR
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin 718281697661.dkr.ecr.eu-west-3.amazonaws.com

# Push
docker push 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest
```

### Étape 5 : Exécuter la Task ECS

```bash
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --region eu-west-3
```

### Étape 6 : Vérifier les logs

```bash
aws logs tail /ecs/forecast-etl --follow --region eu-west-3
```

**Résultat attendu :**
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

### Étape 7 : Vérifier dans MongoDB Atlas

1. Va sur [cloud.mongodb.com](https://cloud.mongodb.com)
2. Clique sur ton cluster → **Browse Collections**
3. Tu devrais voir :
   - Base : `greenandcoop_weather`
   - Collection : `weather_data` (3811 documents)
4. Filtre par `record_type: "measurement"` → 3807 docs
5. Filtre par `record_type: "station_reference"` → 4 docs

---

## 📊 Nouveau schéma MongoDB

### Collection `weather_data`

#### Document type "measurement"
```json
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

#### Document type "station_reference"
```json
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

---

## 🔍 Requêtes utiles pour les Data Scientists

```javascript
// Toutes les mesures
db.weather_data.find({record_type: "measurement"})

// Mesures d'une station spécifique
db.weather_data.find({
    record_type: "measurement",
    station_id: "IICHTE19"
})

// Moyenne température par station
db.weather_data.aggregate([
    {$match: {record_type: "measurement"}},
    {$group: {
        _id: "$station_id",
        avg_temp: {$avg: "$measurements.temperature_celsius"},
        count: {$sum: 1}
    }}
])

// Toutes les stations de référence
db.weather_data.find({record_type: "station_reference"})

// Mesures dans une zone géographique
db.weather_data.find({
    record_type: "measurement",
    "location.latitude": {$gte: 50, $lte: 52},
    "location.longitude": {$gte: 2, $lte: 4}
})
```

---

## ✅ Checklist de validation

- [ ] Tests unitaires passent (`pytest tests/ -v`)
- [ ] Image Docker buildée et pushée vers ECR
- [ ] Anciennes collections supprimées dans Atlas
- [ ] Task ECS exécutée avec succès
- [ ] Collection `weather_data` créée avec 3811 documents
- [ ] Scripts de reporting fonctionnent
- [ ] Documentation mise à jour

---

**Projet Forecast 2.0** - GreenAndCoop  
Dernière mise à jour : Décembre 2024
