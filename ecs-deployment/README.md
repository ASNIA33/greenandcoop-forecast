# 🚀 Guide de Déploiement - Forecast ETL sur AWS ECS

## Fichiers inclus

| Fichier | Description |
|---------|-------------|
| `trust-policy.json` | Politique de confiance pour les rôles IAM |
| `s3-access-policy.json` | Politique d'accès au bucket S3 |
| `task-definition.json` | Définition de la Task ECS |
| `deploy.sh` | Script de déploiement automatisé |

---

## ⚠️ AVANT DE COMMENCER

### 1. Modifie l'URI MongoDB Atlas

Ouvre `task-definition.json` et remplace `REMPLACER_PAR_TON_URI_ATLAS` par ton URI complète :

```json
{
    "name": "MONGO_URI",
    "value": "mongodb+srv://forecast_user:TON_VRAI_MOT_DE_PASSE@forecast-cluster.meeiptz.mongodb.net/?appName=forecast-cluster"
}
```

---

## 🛠️ Méthode 1 : Script automatisé

```bash
# 1. Rends le script exécutable
chmod +x deploy.sh

# 2. Lance le déploiement
./deploy.sh
```

---

## 🛠️ Méthode 2 : Commandes manuelles

### Étape 1 : Créer le rôle d'exécution ECS

```bash
# Vérifier si le rôle existe
aws iam get-role --role-name ecsTaskExecutionRole --region eu-west-3

# Si non, le créer
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://trust-policy.json \
    --region eu-west-3

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
    --region eu-west-3
```

### Étape 2 : Créer le rôle de la Task (accès S3)

```bash
aws iam create-role \
    --role-name forecast-etl-task-role \
    --assume-role-policy-document file://trust-policy.json \
    --region eu-west-3

aws iam put-role-policy \
    --role-name forecast-etl-task-role \
    --policy-name S3AccessPolicy \
    --policy-document file://s3-access-policy.json \
    --region eu-west-3
```

### Étape 3 : Créer le Log Group CloudWatch

```bash
aws logs create-log-group \
    --log-group-name /ecs/forecast-etl \
    --region eu-west-3
```

### Étape 4 : Enregistrer la Task Definition

```bash
aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region eu-west-3
```

### Étape 5 : Lancer la Task

```bash
aws ecs run-task \
    --cluster greenandcoop-cluster \
    --task-definition forecast-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --region eu-west-3
```

---

## 📊 Suivi de l'exécution

### Voir les logs en temps réel

```bash
aws logs tail /ecs/forecast-etl --follow --region eu-west-3
```

### Vérifier le statut de la Task

```bash
# Remplace TASK_ID par l'ID de ta task
aws ecs describe-tasks \
    --cluster greenandcoop-cluster \
    --tasks TASK_ID \
    --region eu-west-3 \
    --query 'tasks[0].lastStatus'
```

### Via la console AWS

1. Va sur [ECS Console](https://eu-west-3.console.aws.amazon.com/ecs/home?region=eu-west-3)
2. Clique sur `greenandcoop-cluster`
3. Onglet **Tasks** → Tu verras ta task en cours
4. Clique dessus pour voir les détails et les logs

---

## ✅ Résultat attendu

Si tout fonctionne, tu devrais voir dans les logs :

```
INFO - -- Début du pipeline du projet Forecast 2.0. --
INFO - [Etape 1/3] : CONNEXION A S3 et RECUPERATION DES FICHIERS...
INFO - Succès : 3 fichiers telechargés depuis S3 vers data/downloaded
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

## 🔧 Dépannage

### Erreur "Task stopped"

```bash
# Voir la raison de l'arrêt
aws ecs describe-tasks \
    --cluster greenandcoop-cluster \
    --tasks TASK_ID \
    --region eu-west-3 \
    --query 'tasks[0].stoppedReason'
```

### Erreur MongoDB timeout

Vérifie que :
1. L'URI MongoDB est correcte dans task-definition.json
2. Le Network Access MongoDB Atlas est configuré sur `0.0.0.0/0`

### Erreur S3 Access Denied

Vérifie que le rôle `forecast-etl-task-role` a bien été créé avec la policy S3.

---

## 💰 Coûts estimés

| Service | Coût par exécution |
|---------|-------------------|
| ECS Fargate (512 CPU, 1GB RAM, ~1 min) | ~$0.01 |
| CloudWatch Logs | Négligeable |
| MongoDB Atlas M0 | Gratuit |
| **Total** | **< $0.02** |
