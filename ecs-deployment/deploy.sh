#!/bin/bash
# =============================================================================
# Script de déploiement ECS - Forecast ETL
# =============================================================================

set -e  # Arrête le script en cas d'erreur

REGION="eu-west-3"
ACCOUNT_ID="718281697661"
CLUSTER_NAME="greenandcoop-cluster"
TASK_FAMILY="forecast-etl"

echo "=========================================="
echo "  Déploiement Forecast ETL sur ECS"
echo "=========================================="

# -----------------------------------------------------------------------------
# ÉTAPE 1 : Créer le rôle d'exécution ECS (si n'existe pas)
# -----------------------------------------------------------------------------
echo ""
echo "[1/5] Vérification du rôle ecsTaskExecutionRole..."

if aws iam get-role --role-name ecsTaskExecutionRole --region $REGION 2>/dev/null; then
    echo "✅ Le rôle ecsTaskExecutionRole existe déjà."
else
    echo "Création du rôle ecsTaskExecutionRole..."
    aws iam create-role \
        --role-name ecsTaskExecutionRole \
        --assume-role-policy-document file://trust-policy.json \
        --region $REGION
    
    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
        --region $REGION
    
    echo "✅ Rôle ecsTaskExecutionRole créé."
fi

# -----------------------------------------------------------------------------
# ÉTAPE 2 : Créer le rôle de la Task (accès S3)
# -----------------------------------------------------------------------------
echo ""
echo "[2/5] Création du rôle forecast-etl-task-role..."

if aws iam get-role --role-name forecast-etl-task-role --region $REGION 2>/dev/null; then
    echo "✅ Le rôle forecast-etl-task-role existe déjà."
else
    aws iam create-role \
        --role-name forecast-etl-task-role \
        --assume-role-policy-document file://trust-policy.json \
        --region $REGION
    
    aws iam put-role-policy \
        --role-name forecast-etl-task-role \
        --policy-name S3AccessPolicy \
        --policy-document file://s3-access-policy.json \
        --region $REGION
    
    echo "✅ Rôle forecast-etl-task-role créé avec accès S3."
fi

# -----------------------------------------------------------------------------
# ÉTAPE 3 : Créer le Log Group CloudWatch
# -----------------------------------------------------------------------------
echo ""
echo "[3/5] Création du Log Group CloudWatch..."

if aws logs describe-log-groups --log-group-name-prefix /ecs/forecast-etl --region $REGION --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "/ecs/forecast-etl"; then
    echo "✅ Le Log Group /ecs/forecast-etl existe déjà."
else
    aws logs create-log-group \
        --log-group-name /ecs/forecast-etl \
        --region $REGION
    echo "✅ Log Group /ecs/forecast-etl créé."
fi

# -----------------------------------------------------------------------------
# ÉTAPE 4 : Enregistrer la Task Definition
# -----------------------------------------------------------------------------
echo ""
echo "[4/5] Enregistrement de la Task Definition..."

aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region $REGION

echo "✅ Task Definition enregistrée."

# -----------------------------------------------------------------------------
# ÉTAPE 5 : Exécuter la Task
# -----------------------------------------------------------------------------
echo ""
echo "[5/5] Lancement de la Task..."

TASK_ARN=$(aws ecs run-task \
    --cluster $CLUSTER_NAME \
    --task-definition $TASK_FAMILY \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-0610fc62ccc083094],securityGroups=[sg-07977d25910df81a9],assignPublicIp=ENABLED}" \
    --region $REGION \
    --query 'tasks[0].taskArn' \
    --output text)

echo "✅ Task lancée !"
echo ""
echo "=========================================="
echo "  DÉPLOIEMENT TERMINÉ"
echo "=========================================="
echo ""
echo "Task ARN : $TASK_ARN"
echo ""
echo "Pour suivre les logs :"
echo "  aws logs tail /ecs/forecast-etl --follow --region $REGION"
echo ""
echo "Pour voir le statut de la task :"
echo "  aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN --region $REGION --query 'tasks[0].lastStatus'"
echo ""
