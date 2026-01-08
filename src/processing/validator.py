"""
Module de validation des données météorologiques.
Utilise Pydantic pour garantir la conformité des données au schéma unifié.

Collection unique : weather_data
- WeatherMeasurement : pour les relevés météo (record_type: "measurement")
- StationReference : pour les métadonnées stations (record_type: "station_reference")
"""

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from typing import Optional, Literal
from datetime import datetime
import pandas as pd


# =============================================================================
# MODÈLES IMBRIQUÉS (sous-documents)
# =============================================================================

class Location(BaseModel):
    """Sous-document pour la localisation géographique."""
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[int] = Field(None, ge=-500, le=9000)  # Mètres

    @field_validator('latitude', 'longitude', 'elevation', mode='before')
    @classmethod
    def handle_nan(cls, v):
        if pd.isna(v) or v == "" or v is None:
            return None
        return v


class Measurements(BaseModel):
    """Sous-document pour les mesures météorologiques."""
    temperature_celsius: Optional[float] = Field(None, ge=-60, le=60)
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = Field(None, ge=0, le=500)
    pressure_hpa: Optional[float] = Field(None, ge=800, le=1200)

    @field_validator('temperature_celsius', 'humidity_percent', 'wind_speed_kmh', 'pressure_hpa', mode='before')
    @classmethod
    def handle_nan(cls, v):
        if pd.isna(v) or v == "" or v is None:
            return None
        return v
    
    @model_validator(mode='after')
    def check_at_least_one_measurement(self):
        """Vérifie qu'au moins une mesure est présente."""
        if all(v is None for v in [
            self.temperature_celsius,
            self.humidity_percent,
            self.wind_speed_kmh,
            self.pressure_hpa
        ]):
            raise ValueError("Au moins une mesure doit être présente")
        return self


class License(BaseModel):
    """Sous-document pour les informations de licence."""
    name: Optional[str] = None
    url: Optional[str] = None
    source_url: Optional[str] = None


# =============================================================================
# MODÈLES PRINCIPAUX
# =============================================================================

class WeatherMeasurement(BaseModel):
    """
    Modèle pour les relevés météorologiques (Weather Underground).
    record_type = "measurement"
    """
    record_type: Literal["measurement"] = "measurement"
    station_id: str = Field(..., min_length=1)
    station_name: Optional[str] = None
    source: str = Field(default="weather_underground")
    location: Location
    timestamp: datetime
    measurements: Measurements

    @field_validator('station_id', mode='before')
    @classmethod
    def validate_station_id(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("station_id est requis")
        return str(v).strip()


class StationReference(BaseModel):
    """
    Modèle pour les stations de référence (InfoClimat).
    record_type = "station_reference"
    """
    record_type: Literal["station_reference"] = "station_reference"
    station_id: str = Field(..., min_length=1)
    station_name: Optional[str] = None
    source: str = Field(default="infoclimat")
    location: Location
    station_type: Optional[str] = "static"
    license: Optional[License] = None
    timestamp: datetime

    @field_validator('station_id', mode='before')
    @classmethod
    def validate_station_id(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("station_id est requis")
        return str(v).strip()


# =============================================================================
# FONCTIONS DE VALIDATION
# =============================================================================

def validate_weather_data(records: list) -> tuple:
    """
    Valide une liste de relevés météorologiques.
    
    Args:
        records: Liste de dictionnaires représentant des mesures
        
    Returns:
        tuple: (valid_records, rejected_records)
    """
    valid_records = []
    rejected_records = []

    for record in records:
        try:
            # Validation Pydantic
            measurement = WeatherMeasurement(**record)
            valid_records.append(measurement.model_dump())
            
        except ValidationError as e:
            # Capture des erreurs précises
            error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            record_copy = record.copy() if isinstance(record, dict) else {"data": str(record)}
            record_copy['rejection_reason'] = "; ".join(error_messages)
            rejected_records.append(record_copy)

    return valid_records, rejected_records


def validate_station_data(records: list) -> tuple:
    """
    Valide une liste de stations de référence.
    
    Args:
        records: Liste de dictionnaires représentant des stations
        
    Returns:
        tuple: (valid_records, rejected_records)
    """
    valid_records = []
    rejected_records = []

    for record in records:
        try:
            # Validation Pydantic
            station = StationReference(**record)
            valid_records.append(station.model_dump())
            
        except ValidationError as e:
            # Capture des erreurs précises
            error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            record_copy = record.copy() if isinstance(record, dict) else {"data": str(record)}
            record_copy['rejection_reason'] = "; ".join(error_messages)
            rejected_records.append(record_copy)

    return valid_records, rejected_records


# =============================================================================
# FONCTION LEGACY (rétrocompatibilité)
# =============================================================================

def validate_data(records: list) -> tuple:
    """
    Fonction de validation générique (rétrocompatibilité).
    Détecte automatiquement le type de données.
    """
    if not records:
        return [], []
    
    # Détection du type basée sur le premier enregistrement
    first_record = records[0]
    
    if first_record.get('record_type') == 'station_reference':
        return validate_station_data(records)
    else:
        return validate_weather_data(records)
