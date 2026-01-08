"""
Script d'audit de la qualité des données MongoDB.
Vérifie la conformité des documents de la collection unifiée 'weather_data'.

Usage:
    python -m src.reporting.check_quality
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
load_dotenv("config/.env")

# Nom de la collection unifiée
COLLECTION_NAME = "weather_data"


def get_mongo_client():
    """Crée un client MongoDB (Atlas ou Local)."""
    atlas_uri = os.getenv("MONGO_URI")
    
    if atlas_uri:
        print("📡 Mode : MongoDB Atlas")
        return MongoClient(atlas_uri, serverSelectionTimeoutMS=30000)
    
    user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    host = os.getenv("MONGO_HOST", "localhost")
    port = os.getenv("MONGO_PORT", "27017")
    rs_name = os.getenv("MONGO_REPLICA_SET")
    
    if rs_name:
        uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&replicaSet={rs_name}"
        print(f"📡 Mode : ReplicaSet Local ({host}:{port})")
    else:
        uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&directConnection=true"
        print(f"📡 Mode : Standalone Local ({host}:{port})")
    
    return MongoClient(uri, serverSelectionTimeoutMS=30000)


def check_measurements_quality(collection):
    """Vérifie la qualité des documents de type 'measurement'."""
    print("\n" + "-" * 60)
    print("📊 TYPE : measurement (relevés météo)")
    print("-" * 60)
    
    total = collection.count_documents({"record_type": "measurement"})
    
    if total == 0:
        print("   ⚠️ Aucune mesure trouvée")
        return 0, 0
    
    print(f"   Total : {total} documents")
    
    # Règles de validation
    validation_rules = {
        "station_id_missing": {
            "record_type": "measurement",
            "$or": [
                {"station_id": {"$exists": False}},
                {"station_id": ""}
            ]
        },
        "timestamp_missing": {
            "record_type": "measurement",
            "timestamp": {"$exists": False}
        },
        "temperature_out_of_range": {
            "record_type": "measurement",
            "$or": [
                {"measurements.temperature_celsius": {"$lt": -60}},
                {"measurements.temperature_celsius": {"$gt": 60}}
            ]
        },
        "humidity_out_of_range": {
            "record_type": "measurement",
            "$or": [
                {"measurements.humidity_percent": {"$lt": 0}},
                {"measurements.humidity_percent": {"$gt": 100}}
            ]
        },
        "location_missing": {
            "record_type": "measurement",
            "$or": [
                {"location": {"$exists": False}},
                {"location.latitude": {"$exists": False}},
                {"location.longitude": {"$exists": False}}
            ]
        }
    }
    
    errors = 0
    for rule_name, query in validation_rules.items():
        try:
            count = collection.count_documents(query)
            status = "✅" if count == 0 else "❌"
            print(f"   {status} {rule_name}: {count}")
            errors += count
        except Exception as e:
            print(f"   ⚠️ {rule_name}: Erreur - {e}")
    
    return total, errors


def check_stations_quality(collection):
    """Vérifie la qualité des documents de type 'station_reference'."""
    print("\n" + "-" * 60)
    print("📍 TYPE : station_reference (métadonnées)")
    print("-" * 60)
    
    total = collection.count_documents({"record_type": "station_reference"})
    
    if total == 0:
        print("   ⚠️ Aucune station de référence trouvée")
        return 0, 0
    
    print(f"   Total : {total} documents")
    
    # Règles de validation
    validation_rules = {
        "station_id_missing": {
            "record_type": "station_reference",
            "$or": [
                {"station_id": {"$exists": False}},
                {"station_id": ""}
            ]
        },
        "station_name_missing": {
            "record_type": "station_reference",
            "$or": [
                {"station_name": {"$exists": False}},
                {"station_name": ""}
            ]
        },
        "location_invalid": {
            "record_type": "station_reference",
            "$or": [
                {"location.latitude": {"$lt": -90}},
                {"location.latitude": {"$gt": 90}},
                {"location.longitude": {"$lt": -180}},
                {"location.longitude": {"$gt": 180}}
            ]
        }
    }
    
    errors = 0
    for rule_name, query in validation_rules.items():
        try:
            count = collection.count_documents(query)
            status = "✅" if count == 0 else "❌"
            print(f"   {status} {rule_name}: {count}")
            errors += count
        except Exception as e:
            print(f"   ⚠️ {rule_name}: Erreur - {e}")
    
    # Liste des stations
    print("\n   📍 Stations référencées :")
    for station in collection.find({"record_type": "station_reference"}, 
                                    {"station_id": 1, "station_name": 1, "source": 1}):
        print(f"      - {station.get('station_id')}: {station.get('station_name')} "
              f"({station.get('source')})")
    
    return total, errors


def check_data_distribution(collection):
    """Analyse la distribution des données."""
    print("\n" + "-" * 60)
    print("📈 DISTRIBUTION DES DONNÉES")
    print("-" * 60)
    
    # Par source
    print("\n   Par source :")
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for doc in collection.aggregate(pipeline):
        print(f"      - {doc['_id']}: {doc['count']} documents")
    
    # Par station (top 5)
    print("\n   Par station (top 5) :")
    pipeline = [
        {"$match": {"record_type": "measurement"}},
        {"$group": {"_id": "$station_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    for doc in collection.aggregate(pipeline):
        print(f"      - {doc['_id']}: {doc['count']} mesures")


def check_data_quality():
    """Fonction principale d'audit."""
    print("=" * 60)
    print("🔍 AUDIT QUALITÉ - Collection Unifiée 'weather_data'")
    print("=" * 60)
    print(f"📅 Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        client = get_mongo_client()
        db = client[os.getenv("MONGO_DB_NAME", "greenandcoop_weather")]
        collection = db[COLLECTION_NAME]
        
        # Total général
        total_docs = collection.count_documents({})
        print(f"\n📊 Collection '{COLLECTION_NAME}' : {total_docs} documents")
        
        if total_docs == 0:
            print("⚠️ Collection vide")
            return 0
        
        # Audit par type
        meas_total, meas_errors = check_measurements_quality(collection)
        stat_total, stat_errors = check_stations_quality(collection)
        
        # Distribution
        check_data_distribution(collection)
        
        # Résumé
        print("\n" + "=" * 60)
        print("📋 RÉSUMÉ DE L'AUDIT")
        print("=" * 60)
        
        total_errors = meas_errors + stat_errors
        error_rate = (total_errors / total_docs * 100) if total_docs > 0 else 0
        
        print(f"\n   Documents totaux       : {total_docs}")
        print(f"   - Mesures météo        : {meas_total}")
        print(f"   - Stations référence   : {stat_total}")
        print(f"\n   Erreurs détectées      : {total_errors}")
        print(f"   Taux d'erreur          : {error_rate:.2f}%")
        
        # Verdict
        print("\n" + "-" * 60)
        if error_rate == 0:
            print("   🏆 VERDICT : QUALITÉ EXCELLENTE")
        elif error_rate < 1:
            print("   ✅ VERDICT : QUALITÉ SATISFAISANTE")
        elif error_rate < 5:
            print("   ⚠️ VERDICT : QUALITÉ ACCEPTABLE")
        else:
            print("   ❌ VERDICT : NETTOYAGE REQUIS")
        print("=" * 60)
        
        client.close()
        return error_rate
        
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)


if __name__ == "__main__":
    check_data_quality()
