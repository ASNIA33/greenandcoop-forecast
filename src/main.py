"""
Pipeline ETL principal - Forecast 2.0
GreenAndCoop - Données météorologiques

Ce script orchestre le pipeline complet :
1. Extraction des données depuis S3
2. Transformation et validation
3. Chargement dans MongoDB (collection unifiée)
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Import des modules internes
from src.connectors.s3_connector import S3Connector
from src.processing.cleaner import process_file
from src.connectors.mongo_connector import MongoConnector

# =============================================================================
# CONFIGURATION DU LOGGING
# =============================================================================

if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
loaded = load_dotenv("config/.env")


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================

def run_pipeline():
    """
    Fonction principale qui orchestre le pipeline ETL.
    
    Étapes :
        1. Extraction : Téléchargement des fichiers depuis S3
        2. Transformation : Nettoyage, conversion, validation
        3. Chargement : Insertion dans MongoDB (collection unifiée)
    """
    logger.info("=" * 60)
    logger.info("-- Début du pipeline du projet Forecast 2.0. --")
    logger.info("=" * 60)

    # ─────────────────────────────────────────────────────────────
    # VÉRIFICATION DES PRÉREQUIS
    # ─────────────────────────────────────────────────────────────
    if not os.getenv("S3_BUCKET_NAME"):
        logger.error("ERREUR CRITIQUE : S3_BUCKET_NAME manquant dans le .env")
        sys.exit(1)

    try:
        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 1 : EXTRACTION (S3 → Local)
        # ─────────────────────────────────────────────────────────────
        logger.info("")
        logger.info("[Étape 1/3] : EXTRACTION - Connexion à S3...")
        
        s3 = S3Connector()
        DOWNLOAD_DIR = "data/downloaded"
        files = s3.download_files(local_dir=DOWNLOAD_DIR)

        if not files:
            logger.warning("Aucun fichier trouvé sur S3 -> Arrêt du pipeline.")
            return

        logger.info(f"✅ {len(files)} fichier(s) téléchargé(s) depuis S3")

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 2 : TRANSFORMATION (Nettoyage + Validation)
        # ─────────────────────────────────────────────────────────────
        logger.info("")
        logger.info("[Étape 2/3] : TRANSFORMATION - Nettoyage et validation...")

        # Liste unifiée de tous les documents
        all_documents = []
        
        # Compteurs pour le reporting
        stats = {
            "files_processed": 0,
            "measurements": 0,
            "station_references": 0,
            "rejected": 0
        }

        for file_path in files:
            filename = os.path.basename(file_path)

            # Reconstruction du chemin complet si nécessaire
            if os.path.dirname(file_path) == "":
                file_path = os.path.join(DOWNLOAD_DIR, filename)
            
            full_path = os.path.abspath(file_path)
            
            if not os.path.exists(full_path):
                logger.error(f"ERREUR: Fichier introuvable : {full_path}")
                continue

            logger.info(f"📄 Traitement : {filename}")
            
            # Transformation (retourne une liste de documents unifiés)
            documents = process_file(full_path, filename)

            if documents:
                # Comptage par type
                for doc in documents:
                    if doc.get('record_type') == 'measurement':
                        stats["measurements"] += 1
                    elif doc.get('record_type') == 'station_reference':
                        stats["station_references"] += 1
                
                all_documents.extend(documents)
                stats["files_processed"] += 1
                logger.info(f"   -> {len(documents)} documents extraits")
            else:
                logger.warning(f"   -> Aucun document extrait")

        # Résumé de la transformation
        total_documents = len(all_documents)
        logger.info("")
        logger.info(f"📊 Résumé transformation :")
        logger.info(f"   - Fichiers traités : {stats['files_processed']}")
        logger.info(f"   - Mesures météo    : {stats['measurements']}")
        logger.info(f"   - Stations réf.    : {stats['station_references']}")
        logger.info(f"   - Total documents  : {total_documents}")

        if total_documents == 0:
            logger.warning("Aucun document à insérer -> Arrêt du pipeline.")
            return

        # ─────────────────────────────────────────────────────────────
        # ÉTAPE 3 : CHARGEMENT (Local → MongoDB)
        # ─────────────────────────────────────────────────────────────
        logger.info("")
        logger.info("[Étape 3/3] : CHARGEMENT - Insertion dans MongoDB...")

        mongo = MongoConnector()
        mongo.connect()
        mongo.init_db()

        # Insertion dans la collection unifiée
        inserted_count = mongo.insert_documents(all_documents)
        
        # Statistiques finales
        final_stats = mongo.get_stats()
        
        logger.info("")
        logger.info(f"📊 Statistiques MongoDB ({final_stats['collection']}) :")
        logger.info(f"   - Total documents      : {final_stats['total']}")
        logger.info(f"   - Mesures météo        : {final_stats['measurements']}")
        logger.info(f"   - Stations référence   : {final_stats['station_references']}")

        # Fermeture de la connexion
        mongo.close()
        
        # ─────────────────────────────────────────────────────────────
        # SUCCÈS
        # ─────────────────────────────────────────────────────────────
        logger.info("")
        logger.info("=" * 60)
        logger.info("=== Pipeline terminé avec succès ! ===")
        logger.info("=" * 60)
        
        # Calcul du taux de réussite
        success_rate = (inserted_count / total_documents * 100) if total_documents > 0 else 0
        logger.info(f"Taux de réussite : {success_rate:.1f}%")

    except Exception as e:
        logger.error(f"❌ Erreur Pipeline : {e}", exc_info=True)
        sys.exit(1)


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    run_pipeline()
