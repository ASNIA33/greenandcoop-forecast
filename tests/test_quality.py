"""
Tests unitaires pour la validation des données (schéma unifié).

Usage:
    pytest tests/test_quality.py -v
"""

import pytest
from datetime import datetime
from src.processing.validator import (
    validate_weather_data,
    validate_station_data,
    WeatherMeasurement,
    StationReference,
    Location,
    Measurements
)


# =============================================================================
# TESTS : WeatherMeasurement (relevés météo)
# =============================================================================

class TestWeatherMeasurement:
    """Tests pour les documents de type 'measurement'."""
    
    def test_valid_measurement(self):
        """Vérifie qu'une mesure correcte passe la validation."""
        raw_data = [{
            "record_type": "measurement",
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
            "timestamp": datetime(2025, 12, 24, 10, 0, 0),
            "measurements": {
                "temperature_celsius": 13.78,
                "humidity_percent": 87,
                "wind_speed_kmh": 13.2,
                "pressure_hpa": 998.3
            }
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 1
        assert len(rejected) == 0
        assert valid[0]["station_id"] == "IICHTE19"
        assert valid[0]["measurements"]["temperature_celsius"] == 13.78
    
    def test_missing_station_id(self):
        """Vérifie le rejet si station_id est manquant."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "",  # Vide
            "timestamp": datetime(2025, 12, 24),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {"temperature_celsius": 15.0}
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1
        assert "station_id" in rejected[0]['rejection_reason']
    
    def test_temperature_out_of_range(self):
        """Vérifie le rejet des températures hors limites."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "TEST01",
            "timestamp": datetime(2025, 12, 24),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {
                "temperature_celsius": 100.0  # Trop chaud (>60)
            }
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1
        assert "temperature_celsius" in rejected[0]['rejection_reason']
    
    def test_humidity_out_of_range(self):
        """Vérifie le rejet des humidités hors limites."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "TEST01",
            "timestamp": datetime(2025, 12, 24),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {
                "temperature_celsius": 15.0,
                "humidity_percent": 150.0  # Impossible (>100)
            }
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1
        assert "humidity_percent" in rejected[0]['rejection_reason']
    
    def test_location_validation(self):
        """Vérifie la validation des coordonnées GPS."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "TEST01",
            "timestamp": datetime(2025, 12, 24),
            "location": {
                "latitude": 200.0,  # Invalide (>90)
                "longitude": 3.0
            },
            "measurements": {"temperature_celsius": 15.0}
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1
    
    def test_partial_measurements(self):
        """Vérifie qu'une mesure partielle (certains champs None) est acceptée."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "TEST01",
            "timestamp": datetime(2025, 12, 24),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {
                "temperature_celsius": 15.0,
                "humidity_percent": None,  # Optionnel
                "wind_speed_kmh": None,    # Optionnel
                "pressure_hpa": None       # Optionnel
            }
        }]
        
        valid, rejected = validate_weather_data(raw_data)
        
        assert len(valid) == 1
        assert len(rejected) == 0


# =============================================================================
# TESTS : StationReference (métadonnées stations)
# =============================================================================

class TestStationReference:
    """Tests pour les documents de type 'station_reference'."""
    
    def test_valid_station(self):
        """Vérifie qu'une station correcte passe la validation."""
        raw_data = [{
            "record_type": "station_reference",
            "station_id": "00052",
            "station_name": "Armentières",
            "source": "infoclimat",
            "location": {
                "city": "Armentières",
                "country": "FR",
                "latitude": 50.689,
                "longitude": 2.877,
                "elevation": 16
            },
            "station_type": "static",
            "license": {
                "name": "CC BY",
                "url": "https://creativecommons.org/licenses/by/2.0/fr/"
            },
            "timestamp": datetime(2025, 12, 24)
        }]
        
        valid, rejected = validate_station_data(raw_data)
        
        assert len(valid) == 1
        assert len(rejected) == 0
        assert valid[0]["station_name"] == "Armentières"
    
    def test_missing_station_id(self):
        """Vérifie le rejet si station_id est manquant."""
        raw_data = [{
            "record_type": "station_reference",
            "station_id": "",
            "station_name": "Test Station",
            "location": {"latitude": 50.0, "longitude": 3.0},
            "timestamp": datetime(2025, 12, 24)
        }]
        
        valid, rejected = validate_station_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1
    
    def test_invalid_coordinates(self):
        """Vérifie le rejet des coordonnées invalides."""
        raw_data = [{
            "record_type": "station_reference",
            "station_id": "TEST01",
            "station_name": "Test Station",
            "location": {
                "latitude": 50.0,
                "longitude": 400.0  # Invalide (>180)
            },
            "timestamp": datetime(2025, 12, 24)
        }]
        
        valid, rejected = validate_station_data(raw_data)
        
        assert len(valid) == 0
        assert len(rejected) == 1


# =============================================================================
# TESTS : Schéma unifié
# =============================================================================

class TestUnifiedSchema:
    """Tests pour le schéma unifié (record_type discriminant)."""
    
    def test_record_type_measurement(self):
        """Vérifie que record_type='measurement' est correctement défini."""
        raw_data = [{
            "record_type": "measurement",
            "station_id": "TEST01",
            "timestamp": datetime.now(),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {"temperature_celsius": 15.0}
        }]
        
        valid, _ = validate_weather_data(raw_data)
        
        assert valid[0]["record_type"] == "measurement"
    
    def test_record_type_station_reference(self):
        """Vérifie que record_type='station_reference' est correctement défini."""
        raw_data = [{
            "record_type": "station_reference",
            "station_id": "TEST01",
            "station_name": "Test",
            "location": {"latitude": 50.0, "longitude": 3.0},
            "timestamp": datetime.now()
        }]
        
        valid, _ = validate_station_data(raw_data)
        
        assert valid[0]["record_type"] == "station_reference"
    
    def test_mixed_batch(self):
        """Vérifie le traitement d'un batch mixte."""
        measurements = [{
            "record_type": "measurement",
            "station_id": "M001",
            "timestamp": datetime.now(),
            "location": {"latitude": 50.0, "longitude": 3.0},
            "measurements": {"temperature_celsius": 15.0}
        }]
        
        stations = [{
            "record_type": "station_reference",
            "station_id": "S001",
            "station_name": "Station Test",
            "location": {"latitude": 50.0, "longitude": 3.0},
            "timestamp": datetime.now()
        }]
        
        valid_m, _ = validate_weather_data(measurements)
        valid_s, _ = validate_station_data(stations)
        
        assert len(valid_m) == 1
        assert len(valid_s) == 1
        assert valid_m[0]["record_type"] == "measurement"
        assert valid_s[0]["record_type"] == "station_reference"
