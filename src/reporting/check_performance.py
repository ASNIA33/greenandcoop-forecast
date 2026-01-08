"""
Script de mesure des performances d'accès à MongoDB.
Teste la collection unifiée 'weather_data'.

Usage:
    python -m src.reporting.check_performance
"""

import time
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

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
        print(f"📡 Mode : ReplicaSet Local")
    else:
        uri = f"mongodb://{user}:{pwd}@{host}:{port}/?authSource=admin&directConnection=true"
        print(f"📡 Mode : Standalone Local")
    
    return MongoClient(uri, serverSelectionTimeoutMS=30000)


def measure_access_time():
    """Mesure les temps d'accès à la collection unifiée."""
    print("=" * 60)
    print("📊 TEST DE PERFORMANCE - Collection Unifiée 'weather_data'")
    print("=" * 60)
    
    try:
        client = get_mongo_client()
        db = client[os.getenv("MONGO_DB_NAME", "greenandcoop_weather")]
        collection = db[COLLECTION_NAME]
        
        # Statistiques de base
        total_docs = collection.count_documents({})
        measurements = collection.count_documents({"record_type": "measurement"})
        stations = collection.count_documents({"record_type": "station_reference"})
        
        print(f"\n📈 Statistiques collection :")
        print(f"   - Total          : {total_docs} documents")
        print(f"   - Mesures        : {measurements}")
        print(f"   - Stations réf.  : {stations}")
        
        if total_docs == 0:
            print("\n⚠️ Collection vide - Tests impossibles")
            return
        
        results = []
        
        # ─────────────────────────────────────────────────────────────
        # TEST 1 : Lecture unitaire (dernière mesure)
        # ─────────────────────────────────────────────────────────────
        print("\n" + "-" * 60)
        print("🔍 Test 1 : Lecture unitaire (dernière mesure)")
        
        start = time.perf_counter()
        doc = collection.find_one(
            {"record_type": "measurement"},
            sort=[("timestamp", -1)]
        )
        elapsed = (time.perf_counter() - start) * 1000
        results.append(("Lecture unitaire", elapsed))
        
        if doc:
            print(f"   Station: {doc.get('station_id')}")
            print(f"   Date: {doc.get('timestamp')}")
        print(f"   ⏱️  Temps : {elapsed:.2f} ms")
        print(f"   {'✅ Excellent' if elapsed < 50 else '⚠️ Acceptable' if elapsed < 100 else '❌ Lent'}")
        
        # ─────────────────────────────────────────────────────────────
        # TEST 2 : Filtrage par type (mesures uniquement)
        # ─────────────────────────────────────────────────────────────
        print("\n" + "-" * 60)
        print("🔍 Test 2 : Filtrage par type (100 mesures)")
        
        start = time.perf_counter()
        docs = list(collection.find({"record_type": "measurement"}).limit(100))
        elapsed = (time.perf_counter() - start) * 1000
        results.append(("Filtrage type", elapsed))
        
        print(f"   Documents récupérés: {len(docs)}")
        print(f"   ⏱️  Temps : {elapsed:.2f} ms")
        print(f"   {'✅ Excellent' if elapsed < 50 else '⚠️ Acceptable' if elapsed < 100 else '❌ Lent'}")
        
        # ─────────────────────────────────────────────────────────────
        # TEST 3 : Filtrage par station
        # ─────────────────────────────────────────────────────────────
        print("\n" + "-" * 60)
        print("🔍 Test 3 : Filtrage par station")
        
        sample = collection.find_one({"record_type": "measurement"})
        station_id = sample.get("station_id") if sample else None
        
        if station_id:
            start = time.perf_counter()
            docs = list(collection.find({
                "record_type": "measurement",
                "station_id": station_id
            }).limit(100))
            elapsed = (time.perf_counter() - start) * 1000
            results.append(("Filtrage station", elapsed))
            
            print(f"   Station: {station_id}")
            print(f"   Documents récupérés: {len(docs)}")
            print(f"   ⏱️  Temps : {elapsed:.2f} ms")
            print(f"   {'✅ Excellent' if elapsed < 50 else '⚠️ Acceptable' if elapsed < 100 else '❌ Lent'}")
        
        # ─────────────────────────────────────────────────────────────
        # TEST 4 : Agrégation - Moyenne température par station
        # ─────────────────────────────────────────────────────────────
        print("\n" + "-" * 60)
        print("🔍 Test 4 : Agrégation (moyenne température par station)")
        
        pipeline = [
            {"$match": {"record_type": "measurement"}},
            {"$group": {
                "_id": "$station_id",
                "avg_temp": {"$avg": "$measurements.temperature_celsius"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        start = time.perf_counter()
        agg_results = list(collection.aggregate(pipeline))
        elapsed = (time.perf_counter() - start) * 1000
        results.append(("Agrégation", elapsed))
        
        for r in agg_results[:3]:
            print(f"   - {r['_id']}: {r['count']} mesures, moy={r['avg_temp']:.2f}°C")
        print(f"   ⏱️  Temps : {elapsed:.2f} ms")
        print(f"   {'✅ Excellent' if elapsed < 100 else '⚠️ Acceptable' if elapsed < 500 else '❌ Lent'}")
        
        # ─────────────────────────────────────────────────────────────
        # TEST 5 : Requête géographique (par région)
        # ─────────────────────────────────────────────────────────────
        print("\n" + "-" * 60)
        print("🔍 Test 5 : Requête géographique (zone France/Belgique)")
        
        start = time.perf_counter()
        docs = list(collection.find({
            "record_type": "measurement",
            "location.latitude": {"$gte": 50, "$lte": 52},
            "location.longitude": {"$gte": 2, "$lte": 4}
        }).limit(100))
        elapsed = (time.perf_counter() - start) * 1000
        results.append(("Requête géo", elapsed))
        
        print(f"   Documents récupérés: {len(docs)}")
        print(f"   ⏱️  Temps : {elapsed:.2f} ms")
        print(f"   {'✅ Excellent' if elapsed < 100 else '⚠️ Acceptable' if elapsed < 500 else '❌ Lent'}")
        
        # ─────────────────────────────────────────────────────────────
        # RÉSUMÉ
        # ─────────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("📋 RÉSUMÉ DES PERFORMANCES")
        print("=" * 60)
        
        for name, time_ms in results:
            print(f"   {name:20} : {time_ms:8.2f} ms")
        
        avg_time = sum(t for _, t in results) / len(results)
        print(f"\n   {'─' * 35}")
        print(f"   {'Temps moyen':20} : {avg_time:8.2f} ms")
        
        # Verdict
        print("\n" + "-" * 60)
        if avg_time < 50:
            print("   🏆 VERDICT : PERFORMANCE EXCELLENTE")
        elif avg_time < 100:
            print("   ✅ VERDICT : PERFORMANCE SATISFAISANTE")
        else:
            print("   ⚠️ VERDICT : OPTIMISATION RECOMMANDÉE")
        print("=" * 60)
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)


if __name__ == "__main__":
    measure_access_time()
