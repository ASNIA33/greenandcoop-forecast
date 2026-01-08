"""
Module de connexion à MongoDB.
Supporte MongoDB Atlas (Cloud) et Docker Compose (Local).

Collection unique : weather_data
"""

import os
import logging
from pymongo import MongoClient, errors, ASCENDING
from pymongo.errors import BulkWriteError

logger = logging.getLogger(__name__)


class MongoConnector:
    """
    Connecteur MongoDB avec détection automatique du mode (Atlas/Local).
    Utilise une collection unique 'weather_data' pour toutes les données.
    """
    
    # Nom de la collection unique
    COLLECTION_NAME = "weather_data"
    
    def __init__(self):
        # Priorité 1 : URI Atlas complète (pour Cloud / ECS)
        atlas_uri = os.getenv("MONGO_URI")
        
        if atlas_uri:
            # Mode Atlas (URI complète fournie)
            self.uri = atlas_uri
            self.mode = "Atlas"
        else:
            # Mode Legacy (variables séparées - pour Docker Compose local)
            user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
            pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
            host = os.getenv("MONGO_HOST", "localhost")
            port = os.getenv("MONGO_PORT", "27017")
            rs_name = os.getenv("MONGO_REPLICA_SET")
            
            if rs_name:
                # Mode Local (Docker Compose avec Replica Set)
                self.uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&replicaSet={rs_name}"
                self.mode = "ReplicaSet"
            else:
                # Mode Cloud (ECS Fargate Standalone)
                self.uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&directConnection=true"
                self.mode = "Standalone"
        
        self.db_name = os.getenv("MONGO_DB_NAME", "greenandcoop_weather")
        self.client = None
        self.db = None
        
        logger.info(f"MongoConnector initialisé en mode: {self.mode}")

    def connect(self):
        """Établissement de la connexion."""
        try:
            # Connexion avec l'URI calculée
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=30000)
            
            # Test de connexion (Ping)
            self.client.admin.command('ping')
            
            # Sélection de la base
            self.db = self.client[self.db_name]
            
            logger.info(f"Connexion réussie ({self.mode}) à la base '{self.db_name}'")
            
        except errors.ServerSelectionTimeoutError as e:
            logger.error(f"Erreur connexion Mongo (Timeout). URI mode '{self.mode}' : {e}")
            raise
        except errors.ConnectionFailure as e:
            logger.error(f"Echec connexion Mongo: {e}")
            raise

    def init_db(self):
        """
        Crée les index pour la collection unifiée.
        Optimisés pour les requêtes des Data Scientists.
        """
        if self.db is None:
            self.connect()

        try:
            collection = self.db[self.COLLECTION_NAME]
            
            # Index 1 : Recherche par station et date (requêtes temporelles)
            collection.create_index(
                [("station_id", ASCENDING), ("timestamp", ASCENDING)],
                name="idx_station_timestamp"
            )
            
            # Index 2 : Filtrage par type de document
            collection.create_index(
                [("record_type", ASCENDING)],
                name="idx_record_type"
            )
            
            # Index 3 : Recherche par source de données
            collection.create_index(
                [("source", ASCENDING)],
                name="idx_source"
            )
            
            # Index 4 : Recherche géographique (si besoin de requêtes geo)
            collection.create_index(
                [("location.latitude", ASCENDING), ("location.longitude", ASCENDING)],
                name="idx_location"
            )
            
            # Index 5 : Unicité pour les stations de référence
            # (évite les doublons de métadonnées)
            collection.create_index(
                [("record_type", ASCENDING), ("station_id", ASCENDING), ("source", ASCENDING)],
                unique=True,
                partialFilterExpression={"record_type": "station_reference"},
                name="idx_unique_station_reference"
            )
            
            logger.info(f"Index MongoDB vérifiés/créés sur '{self.COLLECTION_NAME}'.")
            
        except Exception as e:
            logger.warning(f"Avertissement lors de la création des index : {e}")

    def insert_documents(self, data_list: list):
        """
        Insère des documents dans la collection unifiée.
        Gère les doublons de manière idempotente.
        
        Args:
            data_list: Liste de documents au format unifié
            
        Returns:
            int: Nombre de documents insérés
        """
        if not data_list:
            logger.info("Aucun document à insérer.")
            return 0
        
        if self.db is None:
            self.connect()

        try:
            collection = self.db[self.COLLECTION_NAME]
            
            # ordered=False : Continue même si un document échoue (doublon)
            result = collection.insert_many(data_list, ordered=False)
            count = len(result.inserted_ids)
            
            # Statistiques par type
            measurements = sum(1 for d in data_list if d.get('record_type') == 'measurement')
            stations = sum(1 for d in data_list if d.get('record_type') == 'station_reference')
            
            logger.info(f"-> Succès : {count} documents insérés dans '{self.COLLECTION_NAME}'")
            logger.info(f"   (Mesures: {measurements}, Stations: {stations})")
            
            return count
            
        except BulkWriteError as bwe:
            # Gestion des erreurs "Duplicate Key"
            inserted_count = bwe.details['nInserted']
            duplicates_count = len(bwe.details['writeErrors'])
            
            logger.info(f"Insertion '{self.COLLECTION_NAME}' : {inserted_count} ajoutés, "
                       f"{duplicates_count} doublons ignorés.")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"Erreur critique insertion dans {self.COLLECTION_NAME}: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Retourne les statistiques de la collection.
        
        Returns:
            dict: Statistiques (total, measurements, stations)
        """
        if self.db is None:
            self.connect()
            
        collection = self.db[self.COLLECTION_NAME]
        
        total = collection.count_documents({})
        measurements = collection.count_documents({"record_type": "measurement"})
        stations = collection.count_documents({"record_type": "station_reference"})
        
        return {
            "total": total,
            "measurements": measurements,
            "station_references": stations,
            "collection": self.COLLECTION_NAME
        }

    def close(self):
        """Ferme proprement la connexion."""
        if self.client:
            self.client.close()
            logger.info("Connexion MongoDB fermée.")
