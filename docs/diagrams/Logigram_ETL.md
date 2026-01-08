## 📊 Logigramme du processus ETL

### Processus global

```mermaid
flowchart TD
    START([🚀 DÉBUT]) --> INIT["Initialisation<br/>Chargement .env"]

    INIT --> CHECK_ENV{{"Variables<br/>d'environnement<br/>valides ?"}}
    CHECK_ENV -->|Non| ERROR_ENV[/"❌ ERREUR :<br/>Configuration manquante"/]
    ERROR_ENV --> END_ERROR([🔴 FIN - Échec])

    CHECK_ENV -->|Oui| STEP1["📥 ÉTAPE 1 : EXTRACTION<br/>Connexion à S3"]

    STEP1 --> S3_CONNECT{{"Connexion S3<br/>réussie ?"}}
    S3_CONNECT -->|Non| ERROR_S3[/"❌ ERREUR :<br/>Accès S3 refusé"/]
    ERROR_S3 --> END_ERROR

    S3_CONNECT -->|Oui| DOWNLOAD["Téléchargement des fichiers<br/>vers data/downloaded/"]

    DOWNLOAD --> FILES_EXIST{{"Fichiers<br/>trouvés ?"}}
    FILES_EXIST -->|Non| WARN_EMPTY[/"⚠️ AVERTISSEMENT :<br/>Bucket vide"/]
    WARN_EMPTY --> END_WARN([🟡 FIN - Aucune donnée])

    FILES_EXIST -->|Oui| STEP2["🔄 ÉTAPE 2 : TRANSFORMATION"]

    STEP2 --> LOOP_START{{"Pour chaque<br/>fichier"}}

    LOOP_START --> DETECT_TYPE{{"Type de<br/>fichier ?"}}

    DETECT_TYPE -->|"station_*.jsonl"| TRANSFORM_WEATHER["Transformation météo<br/>• Mapping colonnes<br/>• °F → °C<br/>• mph → km/h<br/>• inHg → hPa"]

    DETECT_TYPE -->|"*info_climat*"| TRANSFORM_STATION["Transformation stations<br/>• Extraction métadonnées<br/>• Normalisation coords"]

    TRANSFORM_WEATHER --> VALIDATE["🔍 Validation Pydantic<br/>• Limites température<br/>• Limites humidité<br/>• Types de données"]

    TRANSFORM_STATION --> STORE_STATIONS[("💾 Stockage temporaire<br/>stations_data[]")]

    VALIDATE --> VALID_CHECK{{"Données<br/>valides ?"}}
    VALID_CHECK -->|Oui| STORE_MEASURES[("💾 Stockage temporaire<br/>measurements_data[]")]
    VALID_CHECK -->|Non| LOG_REJECT[/"📝 LOG :<br/>Motif de rejet"/]
    LOG_REJECT --> STORE_MEASURES

    STORE_MEASURES --> LOOP_END{{"Autres<br/>fichiers ?"}}
    STORE_STATIONS --> LOOP_END
    LOOP_END -->|Oui| LOOP_START

    LOOP_END -->|Non| STEP3["📤 ÉTAPE 3 : CHARGEMENT"]

    STEP3 --> MONGO_CONNECT["Connexion MongoDB Atlas"]

    MONGO_CONNECT --> MONGO_OK{{"Connexion<br/>réussie ?"}}
    MONGO_OK -->|Non| ERROR_MONGO[/"❌ ERREUR :<br/>Timeout MongoDB"/]
    ERROR_MONGO --> END_ERROR

    MONGO_OK -->|Oui| CREATE_INDEX["Création/Vérification<br/>des index"]

    CREATE_INDEX --> INSERT_MEAS["Insertion measurements<br/>ordered=False<br/>(gestion doublons)"]

    INSERT_MEAS --> INSERT_STAT["Insertion stations<br/>ordered=False<br/>(gestion doublons)"]

    INSERT_STAT --> CLOSE_CONN["Fermeture connexion"]

    CLOSE_CONN --> LOG_SUCCESS[/"📝 LOG :<br/>Pipeline terminé avec succès"/]

    LOG_SUCCESS --> END_SUCCESS([🟢 FIN - Succès])
```

### Légende des symboles

| Symbole               | Signification                   |
| --------------------- | ------------------------------- |
| ⬭ (Rectangle arrondi) | Début / Fin                     |
| ▭ (Rectangle)         | Processus / Action              |
| ◇ (Losange)           | Décision / Condition            |
| ▱ (Parallélogramme)   | Entrée / Sortie (logs, erreurs) |
| ⌓ (Cylindre)          | Stockage de données             |

