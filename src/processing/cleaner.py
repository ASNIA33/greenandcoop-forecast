"""
Module de transformation des données météorologiques.
Transforme les fichiers JSONL bruts en documents MongoDB unifiés.

Collection unique : weather_data
- record_type: "measurement" pour les relevés météo
- record_type: "station_reference" pour les métadonnées InfoClimat
"""

import pandas as pd
import json
import logging
import re
from datetime import datetime

# Import du validateur Pydantic
from src.processing.validator import validate_weather_data, validate_station_data

logger = logging.getLogger(__name__)

# --- CONFIGURATION DES MÉTADONNÉES DES STATIONS WEATHER UNDERGROUND ---
STATION_METADATA = {
    "station_la_madelaine_FR.jsonl": {
        "station_id": "ILAMAD25",
        "station_name": "La Madeleine",
        "source": "weather_underground",
        "location": {
            "city": "La Madeleine",
            "country": "FR",
            "latitude": 50.659,
            "longitude": 3.07,
            "elevation": 23
        },
        "hardware": "other",
        "software": "EasyWeatherPro_V5.1.6"
    },
    "station_ichtegem_BE.jsonl": {
        "station_id": "IICHTE19",
        "station_name": "WeerstationBS",
        "source": "weather_underground",
        "location": {
            "city": "Ichtegem",
            "country": "BE",
            "latitude": 51.092,
            "longitude": 2.999,
            "elevation": 15
        },
        "hardware": "other",
        "software": "EasyWeatherV1.6.6"
    }
}


def clean_value(val):
    """
    Nettoie une valeur brute.
    Extrait les nombres des chaînes (ex: "57.0 °F" → 57.0)
    """
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(val))
    if match:
        return float(match.group())
    return None


def fahrenheit_to_celsius(f):
    """Convertit Fahrenheit vers Celsius."""
    if f is None:
        return None
    return round((f - 32) * 5.0 / 9.0, 2)


def mph_to_kmh(mph):
    """Convertit miles/heure vers km/heure."""
    if mph is None:
        return None
    return round(mph * 1.60934, 2)


def inHg_to_hPa(inHg):
    """Convertit pouces de mercure vers hectopascals."""
    if inHg is None:
        return None
    return round(inHg * 33.8639, 1)


def load_airbyte_jsonl(file_path: str) -> pd.DataFrame:
    """
    Lit un fichier JSONL généré par Airbyte.
    Extrait le contenu de '_airbyte_data' pour chaque ligne.
    """
    data_list = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if '_airbyte_data' in record:
                        data_list.append(record['_airbyte_data'])
                except json.JSONDecodeError:
                    continue
        return pd.DataFrame(data_list)
    except Exception as e:
        logger.error(f"Erreur lecture JSONL {file_path}: {e}")
        return pd.DataFrame()


def transform_weather_data(file_path: str, filename: str) -> list:
    """
    Transforme les fichiers de mesures Weather Underground.
    Retourne une liste de documents prêts pour MongoDB (schéma unifié).
    """
    df = load_airbyte_jsonl(file_path)
    
    if df.empty:
        return []

    meta = STATION_METADATA.get(filename, {})
    
    if not meta:
        logger.warning(f"Pas de métadonnées trouvées pour {filename}")
        return []

    # 1. Mapping des colonnes brutes
    column_mapping = {
        'Time': 'time_str',
        'Temperature': 'temp_raw',
        'Humidity': 'humidity_percent',
        'Dew Point': 'dew_point',
        'Wind': 'wind_direction',
        'Speed': 'wind_speed_raw',
        'Gust': 'wind_gust_raw',
        'Pressure': 'pressure_inHg',
        'Precip. Rate.': 'precip_rate',
        'Precip. Accum.': 'precip_accum'
    }
    df.rename(columns=column_mapping, inplace=True)

    # 2. Conversions d'unités
    if 'temp_raw' in df.columns:
        df['temperature_celsius'] = df['temp_raw'].apply(clean_value).apply(fahrenheit_to_celsius)
    if 'wind_speed_raw' in df.columns:
        df['wind_speed_kmh'] = df['wind_speed_raw'].apply(clean_value).apply(mph_to_kmh)
    if 'humidity_percent' in df.columns:
        df['humidity_percent'] = df['humidity_percent'].apply(clean_value)
    if 'pressure_inHg' in df.columns:
        df['pressure_hpa'] = df['pressure_inHg'].apply(clean_value).apply(inHg_to_hPa)

    # 3. Construction du timestamp
    today_str = pd.Timestamp.now().strftime('%Y-%m-%d')
    if 'time_str' in df.columns:
        df['timestamp'] = pd.to_datetime(today_str + ' ' + df['time_str'].astype(str), errors='coerce')
        # Ajout d'un offset pour différencier les relevés de même heure
        df['timestamp'] = df['timestamp'] + pd.to_timedelta(df.index, unit='s')

    # 4. Filtrer les lignes sans timestamp
    df = df.dropna(subset=['timestamp'])

    # 5. Construction des documents au format unifié
    documents = []
    for _, row in df.iterrows():
        doc = {
            "record_type": "measurement",
            "station_id": meta.get("station_id"),
            "station_name": meta.get("station_name"),
            "source": meta.get("source", "weather_underground"),
            "location": meta.get("location", {}),
            "timestamp": row['timestamp'].to_pydatetime() if pd.notna(row['timestamp']) else None,
            "measurements": {
                "temperature_celsius": row.get('temperature_celsius'),
                "humidity_percent": row.get('humidity_percent'),
                "wind_speed_kmh": row.get('wind_speed_kmh'),
                "pressure_hpa": row.get('pressure_hpa')
            }
        }
        documents.append(doc)

    # 6. Validation Pydantic
    valid_data, rejected_data = validate_weather_data(documents)
    
    if rejected_data:
        logger.warning(f"Validation Météo : {len(rejected_data)} lignes rejetées dans {filename}.")
        if len(rejected_data) > 0:
            logger.warning(f"Exemple motif : {rejected_data[0].get('rejection_reason')}")

    logger.info(f"Transformation {filename} : {len(valid_data)} documents valides.")
    return valid_data


def transform_infoclimat(file_path: str) -> list:
    """
    Transforme le fichier InfoClimat (stations de référence).
    Retourne une liste de documents prêts pour MongoDB (schéma unifié).
    """
    try:
        data_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                record = json.loads(line)
                airbyte_data = record.get('_airbyte_data', {})
                
                # Cas 1 : Structure liste 'stations'
                if 'stations' in airbyte_data:
                    data_rows.extend(airbyte_data['stations'])
                # Cas 2 : Structure directe
                elif 'id' in airbyte_data and 'name' in airbyte_data:
                    data_rows.append(airbyte_data)
        
        if not data_rows:
            return []

        # Construction des documents au format unifié
        documents = []
        for station in data_rows:
            # Extraction de la licence
            license_data = station.get('license', {})
            
            doc = {
                "record_type": "station_reference",
                "station_id": str(station.get('id', '')),
                "station_name": station.get('name', ''),
                "source": "infoclimat",
                "location": {
                    "city": station.get('name', ''),
                    "country": "FR",
                    "latitude": float(station.get('latitude', 0)) if station.get('latitude') else None,
                    "longitude": float(station.get('longitude', 0)) if station.get('longitude') else None,
                    "elevation": int(station.get('elevation', 0)) if station.get('elevation') else None
                },
                "station_type": station.get('type', 'static'),
                "license": {
                    "name": license_data.get('license', ''),
                    "url": license_data.get('url', ''),
                    "source_url": license_data.get('metadonnees', '')
                },
                "timestamp": datetime.now()
            }
            documents.append(doc)
        
        # Validation Pydantic
        valid_data, rejected_data = validate_station_data(documents)
        
        if rejected_data:
            logger.warning(f"Validation Stations : {len(rejected_data)} lignes rejetées.")

        logger.info(f"InfoClimat : {len(valid_data)} stations extraites.")
        return valid_data

    except Exception as e:
        logger.error(f"Erreur InfoClimat: {e}")
        return []


def process_file(file_path: str, filename: str) -> list:
    """
    Routeur principal.
    Aiguille le fichier vers la bonne fonction de transformation.
    Retourne une liste de documents au format unifié.
    """
    if "info_climat" in filename or "stations" in filename:
        return transform_infoclimat(file_path)
        
    elif "station_" in filename:
        return transform_weather_data(file_path, filename)
    
    return []
