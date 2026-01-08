```bash
docker exec -it mongo1 mongosh -u admin -p password123 --authenticationDatabase admin
```
```bash
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo-arbiter:27017", arbiterOnly: true }
  ]
})

rs.status().ok
```
```bash
show dbs
show collections
use greenandcoop_weather
db.measurements.countDocuments()
db.stations.countDocuments()
```
Vider la collection
```bash
use greenandcoop_weather
db.measurements.drop()
db.stations.drop()
```

// Doit retourner ~3807
db.measurements.countDocuments()

// Doit retourner 4 (C'est la preuve que cleaner.py fonctionne !)
db.stations.countDocuments()

// Vérifier les index (Tu dois voir 'unique_station_timestamp')
db.measurements.getIndexes()


C'est un sans-faute. J'ai analysé tes 5 fichiers :

docker-compose.yml : La configuration réseau, les volumes persistants et le healthcheck avec start_period sont parfaits.

mongo_connector.py : La logique hybride (Local/Cloud) et la gestion de l'idempotence (init_db, insert_many avec ordered=False) sont implémentées correctement.

validator.py & cleaner.py : La séparation entre la validation stricte (mesures) et souple (stations) est bien là.

main.py : L'orchestration inclut bien l'appel crucial à init_db() avant l'insertion.

Tout est cohérent. Tu as le Feu Vert 🟢.


 docker exec -it mongo1 mongosh -u admin -p password123 --authenticationDatabase admin --eval "rs.status()" | grep "name\|stateStr"



 ### preuves insertion

 #### Vide la base (Reset complet)
 ```bash
 docker exec -it mongo1 mongosh -u admin -p password123 --authenticationDatabase admin --eval "use greenandcoop_weather" --eval "db.measurements.drop(); db.stations.drop()"
 ```
#### Premier passage (L'importation totale)
```bash
docker start -a forecast-etl
```
#### Deuxième passage (La preuve d'idempotence)
> Le log devrait dire : Insertion 'measurements' : 3807 ajoutés, 0 doublons ignorés.

```bash
docker exec -it mongo1 mongosh -u admin -p password123 --authenticationDatabase admin
```

```bash
use greenandcoop_weather

// Compter les mesures
db.measurements.countDocuments()

// Voir un exemple de document pour vérifier le format
db.measurements.findOne()

// Voir l'espace disque utilisé
db.measurements.stats().size / 1024

```

1.3 Récupérer la chaîne de connexion(MongoAtlas)

Dans ton cluster, clique sur "Connect"
Choisis "Drivers"
Sélectionne Python / PyMongo
Copie l'URI, elle ressemble à :

mongodb+srv://forecast_user:b9hJzlOGTN2y4mEu@forecast-cluster.meeiptz.mongodb.net/?appName=forecast-cluster
mongodb+srv://forecast_user:b9hJzlOGTN2y4mEu@forecast-cluster.meeiptz.mongodb.net/?appName=forecast-cluster
OU
mongodb+srv://mbodjabdselam33:uKOipSBHr7AbpYmD@forecast-cluster.meeiptz.mongodb.net/?appName=forecast-cluster
Replace <db_password> with the password for the <db_username> database user.


## Etapes AWS 
### Pousser l'image sur ECR
#### 1- Créer le repository ECR
```bash
# Créer le repository
aws ecr create-repository \
    --repository-name forecast-etl \
    --region eu-west-3

# Récupérer l'URI du repository (note-la)
# Format : 123456789012.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl
```

Récupérer l'URI du repository (note-la)
Format : 123456789012.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl
résultat : 
>{
    "repository": {
        "repositoryArn": "arn:aws:ecr:eu-west-3:718281697661:repository/forecast-etl",
        "registryId": "718281697661",
        "repositoryName": "forecast-etl",
        "repositoryUri": "718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl",
        "createdAt": "2025-12-24T11:29:43.702000+01:00",
        "imageTagMutability": "MUTABLE",
        "imageScanningConfiguration": {
            "scanOnPush": false
        },

#### 2- Build et push l'image
```bash
# Se connecter à ECR
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin 718281697661.dkr.ecr.eu-west-3.amazonaws.com

# Build l'image (depuis le dossier du projet)
docker build --platform linux/amd64 -t forecast-etl .

# Tagger l'image
docker tag forecast-etl:latest 123456789012.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest

# Pousser vers ECR
docker push 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest
```
>⚠️ Important : --platform linux/amd64 est crucial car tu es sur Mac (potentiellement ARM) et ECS Fargate utilise AMD64.

### Créer la Task Definition ECS
#### 1- Créer le rôle IAM pour la task
Ta task ECS a besoin d'accéder à S3. Crée un rôle avec cette policy :

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::ton-bucket-name",
                "arn:aws:s3:::ton-bucket-name/*"
            ]
        }
    ]
}
```


greenandcoop-forecast/
├── README.md                         # Documentation principale ✅
├── Dockerfile                        # ✅
├── docker-compose.yml                # ✅
├── requirements.txt                  # ✅
├── config/.env                       # ✅
├── src/
│   ├── main.py                       # ✅
│   ├── connectors/
│   │   ├── s3_connector.py           # ✅
│   │   └── mongo_connector.py        # ✅ (mis à jour pour Atlas)
│   ├── processing/
│   │   ├── cleaner.py                # ✅
│   │   └── validator.py              # ✅
│   └── reporting/
│       ├── check_performance.py      # ✅ (mis à jour pour Atlas)
│       ├── check_quality.py          # ✅ (mis à jour pour Atlas)
│       └── test_replication.py       # ✅ (mis à jour pour Atlas)
├── tests/
│   └── test_quality.py               # ✅
├── docs/
│   ├── TRANSFORMATION_LOGIC.md       # ✅
│   └── MIGRATION_LOGIC.md            # ✅
└── ecs-deployment/
    ├── task-definition.json          # ✅
    ├── trust-policy.json             # ✅
    └── s3-access-policy.json         # ✅