import sqlite3
import datetime
import json
import logging
from typing import Dict, Any, Optional

import requests
import numpy as np

# Cache SQLite et configuration API
CACHE_DB = "data/data_cache.db"
CACHE_TTL_MINUTES = 30
# Endpoint RainViewer pour les métadonnées radar (JSON public)
RAINVIEWER_MAPS_URL = "https://api.rainviewer.com/public/weather-maps.json"

class WeatherAPIClient:
    #Gère les appels API Open-Meteo et le cache SQLite.
    def __init__(self, db_path: str = CACHE_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        #Initialise la table de cache si inexistante.
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_cache (
                        key TEXT PRIMARY KEY,
                        response TEXT,
                        timestamp DATETIME
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Erreur init DB : {e}")

    def _get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        #Récupère les données en cache si le TTL est respecté.
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT response, timestamp FROM api_cache WHERE key = ?", (key,))
                row = cursor.fetchone()

                if row:
                    cached_response, timestamp_str = row
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                    if datetime.datetime.now() - timestamp < datetime.timedelta(minutes=CACHE_TTL_MINUTES):
                        logging.info(f"Cache hit : {key}")
                        return json.loads(cached_response)
        except Exception as e:
            logging.warning(f"Erreur lecture cache {key} : {e}")
        return None

    def _set_cached_data(self, key: str, data: Dict[str, Any]) -> None:
        #Sauvegarde la réponse API dans le cache local.
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now_str = datetime.datetime.now().isoformat()
                cursor.execute("""
                    INSERT OR REPLACE INTO api_cache (key, response, timestamp)
                    VALUES (?, ?, ?)
                """, (key, json.dumps(data), now_str))
                conn.commit()
        except Exception as e:
            logging.error(f"Erreur écriture cache {key} : {e}")

    def fetch_weather_and_air_quality(self, lat: float, lon: float, mock_mode: bool = False) -> Dict[str, Any]:
        #Récupère les données météo et qualité de l'air (API ou Mock).
        cache_key = f"data_{lat}_{lon}_past1_local"

        if mock_mode:
            return self._generate_mock_data(lat, lon)

        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        # URLs des APIs Open-Meteo
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current_weather=true&past_days=1&timezone=auto"
            f"&hourly=temperature_2m,relativehumidity_2m,surface_pressure,windspeed_10m"
        )
        air_quality_url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
            f"&past_days=1&timezone=auto"
            f"&hourly=pm10,pm2_5,nitrogen_dioxide,ozone,sulphur_dioxide,carbon_monoxide,us_aqi"
        )

        # Appels API et récupération des données
        try:
            logging.info(f"Appel APIs pour ({lat}, {lon})...")
            weather_res = requests.get(weather_url, timeout=5)
            air_res = requests.get(air_quality_url, timeout=5)

            weather_res.raise_for_status()
            air_res.raise_for_status()

            combined = {
                "weather": weather_res.json(),
                "air_quality": air_res.json()
            }
            self._set_cached_data(cache_key, combined)
            return combined

        except requests.exceptions.RequestException as e:
            logging.error(f"Échec API : {e}. Utilisation du mode déconnecté.")
            return self._generate_mock_data(lat, lon)
    # Génération de données de test
    def _generate_mock_data(self, lat: float, lon: float) -> Dict[str, Any]:
        #Génère des données de test pour le mode déconnecté.
        hours = 24 * 7
        now = datetime.datetime.now()
        times = [(now - datetime.timedelta(hours=i)).isoformat() for i in range(hours)][::-1]

        return {
            "weather": {
                "current_weather": {
                    "time": now.replace(minute=0, second=0, microsecond=0).isoformat(),
                    "temperature": round(np.random.uniform(15, 30), 1),
                    "windspeed": round(np.random.uniform(5, 25), 1),
                    "winddirection": int(np.random.uniform(0, 360))
                },
                "hourly": {
                    "time": times,
                    "temperature_2m": np.random.normal(20, 5, hours).tolist(),
                    "relativehumidity_2m": np.random.uniform(40, 90, hours).tolist(),
                    "surface_pressure": np.random.uniform(1000, 1025, hours).tolist(),
                    "windspeed_10m": np.random.uniform(2, 30, hours).tolist()
                }
            },
            "air_quality": {
                "hourly": {
                    "time": times,
                    "pm2_5": np.random.uniform(5, 35, hours).tolist(),
                    "pm10": np.random.uniform(10, 60, hours).tolist(),
                    "nitrogen_dioxide": np.random.uniform(10, 55, hours).tolist(),
                    "ozone": np.random.uniform(20, 80, hours).tolist(),
                    "sulphur_dioxide": np.random.uniform(1, 15, hours).tolist(),
                    "carbon_monoxide": np.random.uniform(100, 500, hours).tolist(),
                    "us_aqi": np.random.randint(15, 120, hours).tolist()
                }
            }
        }

# Récupération des métadonnées radar RainViewer
def fetch_rainviewer_radar(timeout: int = 5) -> Optional[Dict[str, Any]]:
    #Récupère les métadonnées radar RainViewer (frames passé + nowcast).
    try:
        logging.info("Récupération métadonnées RainViewer...")
        response = requests.get(RAINVIEWER_MAPS_URL, timeout=timeout)
        response.raise_for_status()
        return response.json()
    # Gestion des erreurs
    except (requests.exceptions.RequestException, ValueError) as e:
        logging.error(f"Échec RainViewer : {e}")
        return None
