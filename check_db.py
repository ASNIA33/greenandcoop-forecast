import os
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

# Chargement de la config
load_dotenv("config/.env")

def inspect_database():
    print("Ispection de la base de données")
    
    # Connexion (Similaire au connecteur, mais simplifié pour l'analyse)
    user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    uri = f"mongodb://{user}:{pwd}@mongo1:27017/?authSource=admin&replicaSet=rs0"
    
    try:
        client = MongoClient(uri)
        db = client[os.getenv("MONGO_DB_NAME", "greenandcoop_weather")]
        
        # 1. Vérification des Collections
        cols = db.list_collection_names()
        print(f"Collections trouvées : {cols}")
        
        # 2. Analyse des Mesures
        if "measurements" in cols:
            count = db.measurements.count_documents({})
            print(f"\nNombre de relevés météo : {count}")
            
            # Afficher un exemple
            print("Exemple de relevé (Dernier reçu) :")
            last_doc = db.measurements.find_one(sort=[("timestamp", -1)])
            # On enlève l'ID technique pour l'affichage
            if last_doc: del last_doc['_id'] 
            print(last_doc)
            
        # 3. Analyse des Stations
        if "stations" in cols:
            count_stations = db.stations.count_documents({})
            print(f"\nNombre de stations référencées : {count_stations}")

    except Exception as e:
        print(f"Erreur de connexion : {e}")

if __name__ == "__main__":
    inspect_database()

    