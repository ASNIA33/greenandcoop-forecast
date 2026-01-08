# 🔧 Guide des Commandes AWS - Forecast 2.0

Ce document regroupe toutes les commandes AWS CLI utilisées pour déployer et gérer le projet Forecast 2.0.

---

## 📋 Table des matières

1. [Configuration initiale](#-configuration-initiale)
2. [Amazon ECR (Container Registry)](#-amazon-ecr-container-registry)
3. [Amazon ECS (Container Service)](#-amazon-ecs-container-service)
4. [AWS IAM (Gestion des accès)](#-aws-iam-gestion-des-accès)
5. [Amazon CloudWatch (Logs & Monitoring)](#-amazon-cloudwatch-logs--monitoring)
6. [Amazon S3 (Stockage)](#-amazon-s3-stockage)
7. [Amazon EC2 / VPC (Réseau)](#-amazon-ec2--vpc-réseau)
8. [MongoDB Atlas (via mongosh)](#-mongodb-atlas-via-mongosh)
9. [Commandes de diagnostic](#-commandes-de-diagnostic)

---

## 🔐 Configuration initiale

### Vérifier la configuration AWS CLI

```bash
# Vérifier l'identité actuelle
aws sts get-caller-identity

# Résultat attendu :
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "718281697661",
#     "Arn": "arn:aws:iam::718281697661:user/admin-forecast-etl"
# }
```

### Configurer AWS CLI (si pas encore fait)

```bash
# Configuration interactive
aws configure

# Entrer :
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: eu-west-3
# - Default output format: json
```

### Définir la région par défaut

```bash
# Définir la région pour la session
export AWS_DEFAULT_REGION=eu-west-3

# Ou ajouter --region eu-west-3 à chaque commande
```

---

## 🐳 Amazon ECR (Container Registry)

### Créer un repository

```bash
aws ecr create-repository \
    --repository-name forecast-etl \
    --region eu-west-3
```

### Lister les repositories

```bash
aws ecr describe-repositories \
    --region eu-west-3 \
    --query 'repositories[*].[repositoryName,repositoryUri]' \
    --output table
```

### Se connecter à ECR (login Docker)

```bash
aws ecr get-login-password --region eu-west-3 | \
    docker login --username AWS --password-stdin \
    718281697661.dkr.ecr.eu-west-3.amazonaws.com
```

### Construire et pousser une image

```bash
# Build (depuis le dossier du projet)
docker build --platform linux/amd64 -t forecast-etl .

# Tag pour ECR
docker tag forecast-etl:latest \
    718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest

# Push vers ECR
docker push 718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl:latest
```

### Lister les images dans un repository

```bash
aws ecr list-images \
    --repository-name forecast-etl \
    --region eu-west-3
```

### Supprimer une image

```bash
aws ecr batch-delete-image \
    --repository-name forecast-etl \
    --image-ids imageTag=latest \
    --region eu-west-3
```

---

## 🚀 Amazon ECS (Container Service)

### Clusters

```bash
# Lister les clusters
aws ecs list-clusters --region eu-west-3

# Créer un cluster (si nécessaire)
aws ecs create-cluster \
    --cluster-name greenandcoop-cluster \
    --region eu-west-3

# Détails d'un cluster
aws ecs describe-clusters \
    --clusters greenandcoop-cluster \
    --region eu-west-3
```

### Task Definitions

```bash
# Enregistrer une nouvelle Task Definition
aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region eu-west-3

# Lister les Task Definitions
aws ecs list-task-definitions \
    --family-prefix forecast-etl \
    --region eu-west-3

# Détails d'une Task Definition
aws ecs describe-task-definition \
    --task-definition forecast-etl \
    --region eu-west-3

# Supprimer (désenregistrer) une Task Definition
aws ecs deregister-task-definition \
    --task-definition forecast-etl:1 \
    --region eu-west-3
```

### Exécuter une Task

```bash
# Lancer une Task Fargate
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --region eu-west-3

# Avec un override de commande (debug)
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --overrides '{"containerOverrides":[{"name":"forecast-etl","command":["python","-c","print(\"Hello AWS\")"]}]}' \
    --region eu-west-3
```

### Gérer les Tasks

```bash
# Lister les tasks en cours
aws ecs list-tasks \
    --cluster greenandcoop-cluster \
    --region eu-west-3

# Détails d'une task
aws ecs describe-tasks \
    --cluster greenandcoop-cluster \
    --tasks <TASK_ARN> \
    --region eu-west-3

# Statut simplifié
aws ecs describe-tasks \
    --cluster greenandcoop-cluster \
    --tasks <TASK_ARN> \
    --region eu-west-3 \
    --query 'tasks[0].{status:lastStatus,stopped:stoppedReason,startedAt:startedAt}'

# Arrêter une task
aws ecs stop-task \
    --cluster greenandcoop-cluster \
    --task <TASK_ARN> \
    --region eu-west-3
```

---

## 🔑 AWS IAM (Gestion des accès)

### Rôles

```bash
# Créer un rôle
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://trust-policy.json

# Lister les rôles
aws iam list-roles \
    --query 'Roles[?contains(RoleName,`ecs`)].RoleName'

# Détails d'un rôle
aws iam get-role --role-name ecsTaskExecutionRole

# Attacher une policy managée
aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Ajouter une policy inline
aws iam put-role-policy \
    --role-name forecast-etl-task-role \
    --policy-name S3AccessPolicy \
    --policy-document file://s3-access-policy.json

# Lister les policies attachées
aws iam list-attached-role-policies \
    --role-name ecsTaskExecutionRole
```

### Policies

```bash
# Lister les policies inline d'un rôle
aws iam list-role-policies \
    --role-name forecast-etl-task-role

# Voir le contenu d'une policy inline
aws iam get-role-policy \
    --role-name forecast-etl-task-role \
    --policy-name S3AccessPolicy
```

---

## 📊 Amazon CloudWatch (Logs & Monitoring)

### Log Groups

```bash
# Créer un Log Group
aws logs create-log-group \
    --log-group-name /ecs/forecast-etl \
    --region eu-west-3

# Lister les Log Groups
aws logs describe-log-groups \
    --log-group-name-prefix /ecs \
    --region eu-west-3

# Supprimer un Log Group
aws logs delete-log-group \
    --log-group-name /ecs/forecast-etl \
    --region eu-west-3
```

### Consulter les logs

```bash
# Suivre les logs en temps réel (TRÈS UTILE !)
aws logs tail /ecs/forecast-etl --follow --region eu-west-3

# Logs des 10 dernières minutes
aws logs tail /ecs/forecast-etl \
    --since 10m \
    --region eu-west-3

# Logs d'une période spécifique
aws logs filter-log-events \
    --log-group-name /ecs/forecast-etl \
    --start-time $(date -d '1 hour ago' +%s000) \
    --region eu-west-3

# Rechercher un pattern
aws logs filter-log-events \
    --log-group-name /ecs/forecast-etl \
    --filter-pattern "ERROR" \
    --region eu-west-3

# Logs d'un stream spécifique
aws logs get-log-events \
    --log-group-name /ecs/forecast-etl \
    --log-stream-name ecs/forecast-etl/<TASK_ID> \
    --region eu-west-3
```

### Log Streams

```bash
# Lister les streams d'un groupe
aws logs describe-log-streams \
    --log-group-name /ecs/forecast-etl \
    --order-by LastEventTime \
    --descending \
    --region eu-west-3
```

---

## 📦 Amazon S3 (Stockage)

### Buckets

```bash
# Lister les buckets
aws s3 ls

# Créer un bucket
aws s3 mb s3://greenandcoop-forecast-raw-data --region eu-west-3

# Supprimer un bucket (doit être vide)
aws s3 rb s3://nom-du-bucket
```

### Fichiers

```bash
# Lister le contenu d'un bucket
aws s3 ls s3://greenandcoop-forecast-raw-data/

# Lister récursivement
aws s3 ls s3://greenandcoop-forecast-raw-data/ --recursive

# Copier un fichier local vers S3
aws s3 cp fichier.json s3://greenandcoop-forecast-raw-data/

# Télécharger un fichier depuis S3
aws s3 cp s3://greenandcoop-forecast-raw-data/fichier.json ./

# Synchroniser un dossier
aws s3 sync ./data/ s3://greenandcoop-forecast-raw-data/data/

# Supprimer un fichier
aws s3 rm s3://greenandcoop-forecast-raw-data/fichier.json

# Supprimer un dossier
aws s3 rm s3://greenandcoop-forecast-raw-data/dossier/ --recursive
```

---

## 🌐 Amazon EC2 / VPC (Réseau)

### VPC et Subnets

```bash
# Lister les VPCs
aws ec2 describe-vpcs \
    --region eu-west-3 \
    --query 'Vpcs[*].[VpcId,CidrBlock,IsDefault]' \
    --output table

# Lister les subnets
aws ec2 describe-subnets \
    --region eu-west-3 \
    --query 'Subnets[*].[SubnetId,AvailabilityZone,CidrBlock,MapPublicIpOnLaunch]' \
    --output table
```

### Security Groups

```bash
# Lister les Security Groups
aws ec2 describe-security-groups \
    --region eu-west-3 \
    --query 'SecurityGroups[*].[GroupId,GroupName,Description]' \
    --output table

# Détails d'un Security Group
aws ec2 describe-security-groups \
    --group-ids sg-07977d25910df81a9 \
    --region eu-west-3

# Voir les règles entrantes
aws ec2 describe-security-groups \
    --group-ids sg-07977d25910df81a9 \
    --region eu-west-3 \
    --query 'SecurityGroups[0].IpPermissions'

# Voir les règles sortantes
aws ec2 describe-security-groups \
    --group-ids sg-07977d25910df81a9 \
    --region eu-west-3 \
    --query 'SecurityGroups[0].IpPermissionsEgress'

# Ajouter une règle sortante (si nécessaire)
aws ec2 authorize-security-group-egress \
    --group-id sg-07977d25910df81a9 \
    --protocol tcp \
    --port 27017 \
    --cidr 0.0.0.0/0 \
    --region eu-west-3
```

---

## 🍃 MongoDB Atlas (via mongosh)

### Depuis AWS CloudShell

```bash
# 1. Télécharger mongosh
wget https://downloads.mongodb.com/compass/mongosh-2.1.1-linux-x64.tgz

# 2. Extraire
tar -xvzf mongosh-2.1.1-linux-x64.tgz

# 3. Se connecter
./mongosh-2.1.1-linux-x64/bin/mongosh "mongodb+srv://forecast_user:<PASSWORD>@forecast-cluster.meeiptz.mongodb.net/greenandcoop_weather"
```

### Commandes mongosh utiles

```javascript
// Voir les bases de données
show dbs

// Sélectionner la base
use greenandcoop_weather

// Voir les collections
show collections

// Compter les documents
db.measurements.countDocuments()
db.stations.countDocuments()

// Dernier relevé
db.measurements.findOne({}, {sort: {timestamp: -1}})

// Relevés d'une station
db.measurements.find({station_id: "IICHTE19"}).limit(5)

// Moyenne température
db.measurements.aggregate([
    {$group: {_id: null, avg: {$avg: "$temperature_celsius"}}}
])

// Statistiques par station
db.measurements.aggregate([
    {$group: {
        _id: "$station_id",
        count: {$sum: 1},
        avgTemp: {$avg: "$temperature_celsius"}
    }}
])

// Voir les index
db.measurements.getIndexes()

// Quitter
exit
```

---

## 🔍 Commandes de diagnostic

### Vérification complète du déploiement

```bash
#!/bin/bash
# Script de diagnostic rapide

echo "=== Vérification AWS Forecast 2.0 ==="

echo -e "\n📦 ECR - Image Docker:"
aws ecr describe-images \
    --repository-name forecast-etl \
    --region eu-west-3 \
    --query 'imageDetails[0].{pushedAt:imagePushedAt,size:imageSizeInBytes}' \
    --output table

echo -e "\n🚀 ECS - Dernière Task:"
TASK_ARN=$(aws ecs list-tasks \
    --cluster greenandcoop-cluster \
    --region eu-west-3 \
    --query 'taskArns[0]' \
    --output text)

if [ "$TASK_ARN" != "None" ]; then
    aws ecs describe-tasks \
        --cluster greenandcoop-cluster \
        --tasks $TASK_ARN \
        --region eu-west-3 \
        --query 'tasks[0].{status:lastStatus,startedAt:startedAt}'
else
    echo "Aucune task en cours"
fi

echo -e "\n📊 CloudWatch - Derniers logs:"
aws logs tail /ecs/forecast-etl \
    --since 1h \
    --region eu-west-3 \
    --max-items 5

echo -e "\n✅ Diagnostic terminé"
```

### Problèmes courants

```bash
# Task qui s'arrête immédiatement
aws ecs describe-tasks \
    --cluster greenandcoop-cluster \
    --tasks <TASK_ARN> \
    --region eu-west-3 \
    --query 'tasks[0].{status:lastStatus,reason:stoppedReason,code:stopCode}'

# Erreurs dans les logs
aws logs filter-log-events \
    --log-group-name /ecs/forecast-etl \
    --filter-pattern "ERROR" \
    --region eu-west-3

# Vérifier les permissions du rôle
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::718281697661:role/forecast-etl-task-role \
    --action-names s3:GetObject \
    --resource-arns arn:aws:s3:::greenandcoop-forecast-raw-data/*
```

---

## 📝 Variables d'environnement utiles

```bash
# Ajouter à ~/.bashrc ou ~/.zshrc

export AWS_DEFAULT_REGION=eu-west-3
export AWS_ACCOUNT_ID=718281697661
export ECR_REPO=718281697661.dkr.ecr.eu-west-3.amazonaws.com/forecast-etl
export ECS_CLUSTER=greenandcoop-cluster
export ECS_TASK=forecast-etl

# Alias utiles
alias ecr-login='aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin $ECR_REPO'
alias ecs-logs='aws logs tail /ecs/forecast-etl --follow --region eu-west-3'
alias ecs-run='aws ecs run-task --cluster $ECS_CLUSTER --task-definition $ECS_TASK --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" --region eu-west-3'
```

---

## 🔗 Liens utiles

| Service | Console AWS |
|---------|-------------|
| ECS | [Console ECS](https://eu-west-3.console.aws.amazon.com/ecs/home?region=eu-west-3) |
| ECR | [Console ECR](https://eu-west-3.console.aws.amazon.com/ecr/repositories?region=eu-west-3) |
| CloudWatch | [Console CloudWatch](https://eu-west-3.console.aws.amazon.com/cloudwatch/home?region=eu-west-3) |
| S3 | [Console S3](https://s3.console.aws.amazon.com/s3/home?region=eu-west-3) |
| IAM | [Console IAM](https://console.aws.amazon.com/iam/home) |

---

- [README Principal](./README.md) - Vue d'ensemble du projet


**Projet Forecast 2.0** - GreenAndCoop  
Région AWS : `eu-west-3` (Paris)  
Dernière mise à jour : Décembre 2024

