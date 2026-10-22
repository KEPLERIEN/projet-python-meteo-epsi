from typing import Dict, List

import pandas as pd

# Seuils d'alerte (OMS)
THRESHOLDS = {
    "pm2_5": {"warning": 15.0, "danger": 25.0, "unit": "µg/m³"},
    "pm10": {"warning": 45.0, "danger": 50.0, "unit": "µg/m³"},
    "no2": {"warning": 25.0, "danger": 50.0, "unit": "µg/m³"},
    "temp_max": {"warning": 33.0, "danger": 38.0, "unit": "°C"}
}

def detect_alerts(df: pd.DataFrame) -> List[Dict[str, str]]:
    #Analyse les données récentes pour détecter les dépassements de seuils.
    alerts = []
    if df.empty:
        return alerts

    latest = df.iloc[-1]

    # Vérification PM2.5
    if latest["pm2_5"] >= THRESHOLDS["pm2_5"]["danger"]:
        alerts.append({
            "level": "danger",
            "message": f"Alerte Rouge Pollution (PM2.5) : {latest['pm2_5']:.1f} {THRESHOLDS['pm2_5']['unit']} (Seuil: {THRESHOLDS['pm2_5']['danger']})"
        })
    elif latest["pm2_5"] >= THRESHOLDS["pm2_5"]["warning"]:
        alerts.append({
            "level": "warning",
            "message": f"Vigilance Pollution (PM2.5) : {latest['pm2_5']:.1f} {THRESHOLDS['pm2_5']['unit']}"
        })

    # Vérification NO2
    if latest["nitrogen_dioxide"] >= THRESHOLDS["no2"]["danger"]:
        alerts.append({
            "level": "danger",
            "message": f"Alerte Dépassement NO2 : {latest['nitrogen_dioxide']:.1f} µg/m³"
        })

    # Vérification Température
    if latest["temperature_2m"] >= THRESHOLDS["temp_max"]["warning"]:
        alerts.append({
            "level": "warning",
            "message": f"Vigilance Forte Chaleur / Canicule : {latest['temperature_2m']:.1f} °C"
        })

    return alerts
