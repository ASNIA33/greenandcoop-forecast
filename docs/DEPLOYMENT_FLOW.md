# 🚀 Logigramme de Déploiement

Ce document décrit le processus complet de déploiement du pipeline ETL Forecast 2.0, du développement local jusqu'à l'exécution sur AWS.

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Logigramme de déploiement](#-logigramme-de-déploiement)
3. [Détail des étapes](#-détail-des-étapes)
4. [Environnements](#-environnements)

---

## 🎯 Vue d'ensemble

Le déploiement suit un flux en 3 phases :

| Phase | Description | Outils |
|-------|-------------|--------|
| **1. Build** | Construction de l'image Docker | Docker, Dockerfile |
| **2. Push** | Publication sur le registry AWS | ECR, AWS CLI |
| **3. Run** | Exécution sur le cloud | ECS Fargate |

---

## 📊 Logigramme de déploiement

```mermaid
flowchart TD
    subgraph DEV["💻 PHASE 1 : DÉVELOPPEMENT LOCAL"]
        START([🚀 DÉBUT]) --> CODE["Modification du code<br/>src/*.py"]
        CODE --> TEST_LOCAL{{"Tests locaux<br/>passent ?"}}
        TEST_LOCAL -->|Non| CODE
        TEST_LOCAL -->|Oui| DOCKER_COMPOSE["Test Docker Compose<br/>docker-compose up"]
        DOCKER_COMPOSE --> LOCAL_OK{{"Pipeline local<br/>fonctionne ?"}}
        LOCAL_OK -->|Non| CODE
        LOCAL_OK -->|Oui| BUILD_PHASE
    end

    subgraph BUILD["🐳 PHASE 2 : BUILD & PUSH"]
        BUILD_PHASE["Préparation déploiement"]
        BUILD_PHASE --> DOCKER_BUILD["docker build<br/>--platform linux/amd64"]
        DOCKER_BUILD --> BUILD_OK{{"Build<br/>réussi ?"}}
        BUILD_OK -->|Non| FIX_DOCKERFILE["Corriger Dockerfile<br/>ou dépendances"]
        FIX_DOCKERFILE --> DOCKER_BUILD
        BUILD_OK -->|Oui| ECR_LOGIN["aws ecr get-login-password<br/>docker login"]
        ECR_LOGIN --> DOCKER_TAG["docker tag<br/>→ ECR URI"]
        DOCKER_TAG --> DOCKER_PUSH["docker push<br/>→ ECR"]
        DOCKER_PUSH --> PUSH_OK{{"Push<br/>réussi ?"}}
        PUSH_OK -->|Non| ECR_LOGIN
        PUSH_OK -->|Oui| DEPLOY_PHASE
    end

    subgraph DEPLOY["☁️ PHASE 3 : DÉPLOIEMENT AWS"]
        DEPLOY_PHASE["Mise à jour ECS"]
        DEPLOY_PHASE --> UPDATE_TASK{{"Task Definition<br/>modifiée ?"}}
        UPDATE_TASK -->|Oui| REGISTER_TASK["aws ecs register-task-definition"]
        UPDATE_TASK -->|Non| RUN_TASK
        REGISTER_TASK --> RUN_TASK["aws ecs run-task<br/>--launch-type FARGATE"]
        RUN_TASK --> TASK_STARTED{{"Task<br/>démarrée ?"}}
        TASK_STARTED -->|Non| CHECK_CONFIG["Vérifier :<br/>• Security Group<br/>• Subnets<br/>• IAM Roles"]
        CHECK_CONFIG --> RUN_TASK
        TASK_STARTED -->|Oui| MONITOR
    end

    subgraph MONITOR["📈 PHASE 4 : MONITORING"]
        MONITOR["aws logs tail --follow"]
        MONITOR --> PIPELINE_OK{{"Pipeline<br/>terminé OK ?"}}
        PIPELINE_OK -->|Non| ANALYZE_LOGS["Analyser les logs<br/>CloudWatch"]
        ANALYZE_LOGS --> ERROR_TYPE{{"Type<br/>d'erreur ?"}}
        ERROR_TYPE -->|"Code"| CODE
        ERROR_TYPE -->|"Config AWS"| CHECK_CONFIG
        ERROR_TYPE -->|"MongoDB"| CHECK_ATLAS["Vérifier :<br/>• Network Access<br/>• Credentials"]
        CHECK_ATLAS --> RUN_TASK
        PIPELINE_OK -->|Oui| VERIFY_DATA
    end

    subgraph VALIDATION["✅ PHASE 5 : VALIDATION"]
        VERIFY_DATA["Vérification MongoDB Atlas<br/>Browse Collections"]
        VERIFY_DATA --> DATA_OK{{"Données<br/>insérées ?"}}
        DATA_OK -->|Non| ANALYZE_LOGS
        DATA_OK -->|Oui| END_SUCCESS([🟢 DÉPLOIEMENT RÉUSSI])
    end
```

---

## 📝 Détail des étapes

### Phase 1 : Développement local

| Étape | Commande | Description |
|-------|----------|-------------|
| Tests unitaires | `pytest tests/` | Validation du code |
| Test Docker Compose | `docker-compose up` | Test avec MongoDB local |
| Vérification logs | `docker logs forecast-etl` | S'assurer que le pipeline fonctionne |

### Phase 2 : Build & Push

| Étape | Commande | Description |
|-------|----------|-------------|
| Build image | `docker build --platform linux/amd64 -t forecast-etl .` | Construction pour architecture AMD64 |
| Login ECR | `aws ecr get-login-password \| docker login` | Authentification au registry |
| Tag image | `docker tag forecast-etl:latest <ECR_URI>:latest` | Préparation pour push |
| Push image | `docker push <ECR_URI>:latest` | Upload vers ECR |

### Phase 3 : Déploiement AWS

| Étape | Commande | Description |
|-------|----------|-------------|
| Register Task | `aws ecs register-task-definition --cli-input-json file://task-definition.json` | Mise à jour de la définition |
| Run Task | `aws ecs run-task --cluster greenandcoop-cluster --task-definition forecast-etl ...` | Lancement du conteneur |

### Phase 4 : Monitoring

| Étape | Commande | Description |
|-------|----------|-------------|
| Logs temps réel | `aws logs tail /ecs/forecast-etl --follow` | Suivi de l'exécution |
| Statut task | `aws ecs describe-tasks --cluster ... --tasks <ARN>` | Vérification du statut |

### Phase 5 : Validation

| Étape | Action | Description |
|-------|--------|-------------|
| MongoDB Atlas | Browse Collections | Vérifier les documents insérés |
| Scripts reporting | `python -m src.reporting.check_quality` | Audit qualité |

---

## 🔄 Logigramme simplifié (Quick Reference)

```mermaid
flowchart LR
    subgraph LOCAL["💻 Local"]
        A["Code"] --> B["Test"]
    end
    
    subgraph BUILD["🐳 Build"]
        C["docker build"] --> D["docker push"]
    end
    
    subgraph AWS["☁️ AWS"]
        E["ECS run-task"] --> F["CloudWatch"]
    end
    
    subgraph DB["🍃 MongoDB"]
        G["Atlas"]
    end
    
    LOCAL --> BUILD --> AWS --> DB
```

---

## 🌍 Environnements

### Comparaison Local vs Production

```mermaid
flowchart TB
    subgraph LOCAL["💻 Environnement LOCAL"]
        direction TB
        L_CODE["Code Python"]
        L_DOCKER["Docker Compose"]
        L_MONGO["MongoDB ReplicaSet<br/>mongo1 + mongo2 + arbiter"]
        L_DATA["data/downloaded/"]
        
        L_CODE --> L_DOCKER --> L_MONGO
        L_DOCKER --> L_DATA
    end
    
    subgraph PROD["☁️ Environnement PRODUCTION (AWS)"]
        direction TB
        P_ECR["ECR<br/>Image Docker"]
        P_ECS["ECS Fargate<br/>Container"]
        P_S3["S3<br/>Données brutes"]
        P_ATLAS["MongoDB Atlas<br/>ReplicaSet 3 nœuds"]
        P_CW["CloudWatch<br/>Logs"]
        
        P_ECR --> P_ECS
        P_ECS --> P_S3
        P_ECS --> P_ATLAS
        P_ECS --> P_CW
    end
```

### Variables d'environnement par environnement

| Variable | Local (Docker Compose) | Production (ECS) |
|----------|------------------------|------------------|
| `MONGO_URI` | ❌ Non défini | ✅ `mongodb+srv://...` |
| `MONGO_HOST` | `mongo1` | ❌ Non défini |
| `MONGO_REPLICA_SET` | `rs0` | ❌ Non défini |
| `S3_BUCKET_NAME` | `greenandcoop-forecast-raw-data` | `greenandcoop-forecast-raw-data` |
| `AWS_REGION` | `eu-west-3` | `eu-west-3` |

---

## 🔧 Commandes rapides

```bash
# BUILD & PUSH ===
docker build --platform linux/amd64 -t forecast-etl .
docker tag forecast-etl:latest 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin 718281697661.dkr.ecr.eu-west-3.amazonaws.com
docker push 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest

# DEPLOY
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --region eu-west-3

# MONITOR
aws logs tail /ecs/forecast-etl --follow --region eu-west-3
```

---

## 📊 Légende des symboles

| Symbole | Forme Mermaid | Signification |
|---------|---------------|---------------|
| ⬭ | `([texte])` | Début / Fin |
| ▭ | `[texte]` | Processus / Action |
| ◇ | `{{texte}}` | Décision / Condition |
| ▱ | `[/texte/]` | Entrée / Sortie |
| ⬡ | `subgraph` | Regroupement / Phase |

---

## 🔗 Documents liés

- [README Principal](../README.md) - Architecture technique
- [Commandes AWS](../AWS_COMMANDS.md) - Référence CLI
- [Migration Logic](MIGRATION_LOGIC.md) - Processus de chargement

---

