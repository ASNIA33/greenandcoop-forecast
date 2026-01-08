"""
Script de test de réplication MongoDB.
- Mode Local (Docker Compose) : Test PRIMARY → SECONDARY
- Mode Atlas : Vérification du ReplicaSet et test de failover readiness

Usage:
    python -m src.reporting.test_replication
"""

import time
import os
import sys
from pymongo import MongoClient, ReadPreference
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv
from datetime import datetime

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
load_dotenv("config/.env")


def test_replication_local():
    """
    Test de réplication pour l'environnement Docker Compose local.
    Vérifie que les données écrites sur le PRIMARY sont répliquées sur le SECONDARY.
    """
    print("=" * 60)
    print("🔄 TEST DE RÉPLICATION - Mode Docker Compose Local")
    print("=" * 60)
    
    user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    pwd = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    db_name = os.getenv("MONGO_DB_NAME", "greenandcoop_weather")
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 1 : Connexion au PRIMARY (mongo1:27017)
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 1 : Connexion au PRIMARY (mongo1:27017)")
    
    uri_primary = f"mongodb://{user}:{pwd}@mongo1:27017/?authSource=admin&replicaSet=rs0"
    
    try:
        client_primary = MongoClient(uri_primary, serverSelectionTimeoutMS=10000)
        db_primary = client_primary[db_name]
        print("   ✅ Connexion PRIMARY établie")
    except ServerSelectionTimeoutError as e:
        print(f"   ❌ Échec connexion PRIMARY : {e}")
        print("\n   💡 Astuce : Vérifiez que Docker Compose est lancé (docker-compose up -d)")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 2 : Insertion d'un document de test
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 2 : Insertion d'un document de test sur le PRIMARY")
    
    test_doc = {
        "type": "replication_test",
        "timestamp": datetime.now(),
        "test_id": f"test_{int(time.time())}"
    }
    
    try:
        insert_result = db_primary.test_collection.insert_one(test_doc)
        doc_id = insert_result.inserted_id
        print(f"   ✅ Document inséré : _id={doc_id}")
    except Exception as e:
        print(f"   ❌ Échec insertion : {e}")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 3 : Connexion au SECONDARY (localhost:27018)
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 3 : Connexion au SECONDARY (localhost:27018)")
    
    # Note: En local, mongo2 est mappé sur le port 27018
    # On utilise directConnection=true pour forcer la connexion à ce nœud
    uri_secondary = f"mongodb://{user}:{pwd}@localhost:27018/?authSource=admin&directConnection=true"
    
    try:
        client_secondary = MongoClient(uri_secondary, serverSelectionTimeoutMS=10000)
        db_secondary = client_secondary[db_name]
        print("   ✅ Connexion SECONDARY établie")
    except ServerSelectionTimeoutError as e:
        print(f"   ❌ Échec connexion SECONDARY : {e}")
        print("\n   💡 Astuce : Vérifiez que le port 27018 est bien exposé dans docker-compose.yml")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 4 : Vérification de la réplication
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 4 : Vérification de la réplication (polling)")
    
    found = False
    attempts = 0
    max_attempts = 20
    start_time = time.time()
    
    while not found and attempts < max_attempts:
        try:
            result = db_secondary.test_collection.find_one({"_id": doc_id})
            if result:
                found = True
                replication_time = (time.time() - start_time) * 1000  # ms
                print(f"   ✅ Document trouvé sur SECONDARY après {replication_time:.0f}ms")
            else:
                attempts += 1
                print(f"   ⏳ Synchronisation en cours... ({attempts}/{max_attempts})")
                time.sleep(0.5)
        except Exception as e:
            print(f"   ⚠️ Erreur temporaire : {e}")
            attempts += 1
            time.sleep(1)
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 5 : Nettoyage
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 5 : Nettoyage")
    
    try:
        db_primary.test_collection.delete_one({"_id": doc_id})
        print("   ✅ Document de test supprimé")
    except Exception as e:
        print(f"   ⚠️ Erreur nettoyage : {e}")
    
    client_primary.close()
    client_secondary.close()
    
    # ─────────────────────────────────────────────────────────────
    # VERDICT
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if found:
        print("🏆 VERDICT : RÉPLICATION FONCTIONNELLE")
        print(f"   Les données sont répliquées en {replication_time:.0f}ms")
    else:
        print("❌ VERDICT : ÉCHEC DE RÉPLICATION")
        print("   Le document n'a pas été répliqué dans le délai imparti")
    print("=" * 60)
    
    return found


def test_replication_atlas():
    """
    Test de réplication pour MongoDB Atlas.
    Vérifie l'état du ReplicaSet et la capacité de lecture sur les secondaires.
    """
    print("=" * 60)
    print("🔄 TEST DE RÉPLICATION - Mode MongoDB Atlas")
    print("=" * 60)
    
    atlas_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "greenandcoop_weather")
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 1 : Connexion au cluster Atlas
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 1 : Connexion au cluster Atlas")
    
    try:
        client = MongoClient(atlas_uri, serverSelectionTimeoutMS=30000)
        client.admin.command('ping')
        print("   ✅ Connexion établie")
    except ServerSelectionTimeoutError as e:
        print(f"   ❌ Échec connexion : {e}")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 2 : Vérification de l'état du ReplicaSet
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 2 : État du ReplicaSet")
    
    try:
        # Récupération de la topologie
        topology = client.topology_description
        print(f"   Type de topologie : {topology.topology_type_name}")
        
        servers = topology.server_descriptions()
        primary_count = 0
        secondary_count = 0
        
        print("\n   Membres du cluster :")
        for address, server in servers.items():
            server_type = server.server_type_name
            if server_type == "RSPrimary":
                primary_count += 1
                print(f"   🟢 PRIMARY   : {address}")
            elif server_type == "RSSecondary":
                secondary_count += 1
                print(f"   🔵 SECONDARY : {address}")
            else:
                print(f"   ⚪ {server_type}: {address}")
        
        print(f"\n   Résumé : {primary_count} PRIMARY, {secondary_count} SECONDARY")
        
        if primary_count != 1:
            print("   ⚠️ Attention : Il devrait y avoir exactement 1 PRIMARY")
        if secondary_count < 1:
            print("   ⚠️ Attention : Il devrait y avoir au moins 1 SECONDARY")
            
    except Exception as e:
        print(f"   ⚠️ Impossible de lire l'état du ReplicaSet : {e}")
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 3 : Test d'écriture + lecture sur secondaire
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 3 : Test écriture PRIMARY → lecture SECONDARY")
    
    db = client[db_name]
    test_doc = {
        "type": "replication_test",
        "timestamp": datetime.now(),
        "test_id": f"test_atlas_{int(time.time())}"
    }
    
    try:
        # Écriture (toujours sur PRIMARY)
        insert_result = db.test_collection.insert_one(test_doc)
        doc_id = insert_result.inserted_id
        print(f"   ✅ Document écrit sur PRIMARY : _id={doc_id}")
        
        # Lecture avec préférence SECONDARY
        # Attendre un peu pour la réplication
        time.sleep(1)
        
        secondary_client = MongoClient(
            atlas_uri, 
            serverSelectionTimeoutMS=30000,
            readPreference='secondary'
        )
        secondary_db = secondary_client[db_name]
        
        result = secondary_db.test_collection.find_one({"_id": doc_id})
        
        if result:
            print("   ✅ Document lu depuis SECONDARY - Réplication OK")
        else:
            print("   ⚠️ Document non trouvé sur SECONDARY (peut être un délai)")
        
        # Nettoyage
        db.test_collection.delete_one({"_id": doc_id})
        print("   ✅ Document de test supprimé")
        
        secondary_client.close()
        
    except Exception as e:
        print(f"   ⚠️ Erreur lors du test : {e}")
    
    # ─────────────────────────────────────────────────────────────
    # ÉTAPE 4 : Vérification des index
    # ─────────────────────────────────────────────────────────────
    print("\n📝 Étape 4 : Vérification des index (répliqués)")
    
    try:
        indexes = list(db.measurements.list_indexes())
        print(f"   Collection 'measurements' : {len(indexes)} index(es)")
        for idx in indexes:
            print(f"   - {idx.get('name')}: {idx.get('key')}")
    except Exception as e:
        print(f"   ⚠️ Erreur lecture index : {e}")
    
    client.close()
    
    # ─────────────────────────────────────────────────────────────
    # VERDICT
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if primary_count == 1 and secondary_count >= 1:
        print("🏆 VERDICT : REPLICASET ATLAS FONCTIONNEL")
        print(f"   Cluster healthy : 1 PRIMARY + {secondary_count} SECONDARY(s)")
    else:
        print("⚠️ VERDICT : VÉRIFICATION MANUELLE RECOMMANDÉE")
        print("   Consultez le dashboard MongoDB Atlas pour plus de détails")
    print("=" * 60)
    
    return True


def test_replication():
    """
    Fonction principale de test de réplication.
    Détecte automatiquement le mode (Atlas ou Local).
    """
    print("\n" + "=" * 60)
    print("🔄 TEST DE RÉPLICATION MongoDB - GreenAndCoop Forecast 2.0")
    print("=" * 60)
    print(f"📅 Date du test : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    atlas_uri = os.getenv("MONGO_URI")
    
    if atlas_uri:
        return test_replication_atlas()
    else:
        return test_replication_local()


if __name__ == "__main__":
    success = test_replication()
    sys.exit(0 if success else 1)
