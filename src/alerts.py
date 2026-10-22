from typing import Dict, List

import pandas as pd

# Seuils d'alerte (OMS)
# Seuils basés sur les lignes directrices de l'OMS (2021)
# warning = valeur guide (AQG) | danger = cible intermédiaire de l'OMS
THRESHOLDS = {
    "pm2_5": {"warning": 15.0, "danger": 25.0, "unit": "µg/m³"},             # AQG 24 h / cible interm. 4
    "pm10": {"warning": 45.0, "danger": 50.0, "unit": "µg/m³"},              # AQG 24 h / cible interm. 4
    "no2": {"warning": 25.0, "danger": 50.0, "unit": "µg/m³"},               # AQG 24 h / cible interm. 2
    "ozone": {"warning": 100.0, "danger": 120.0, "unit": "µg/m³"},           # AQG 8 h / cible interm. 2
    "sulphur_dioxide": {"warning": 40.0, "danger": 50.0, "unit": "µg/m³"},   # AQG 24 h / cible interm. 2
    "carbon_monoxide": {"warning": 4000.0, "danger": 10000.0, "unit": "µg/m³"},  # AQG 24 h (4 mg/m³) / AQG 8 h (10 mg/m³)
    "us_aqi": {"warning": 50, "danger": 100, "unit": ""},                    # échelle EPA, pas OMS
    "temp_max": {"warning": 33.0, "danger": 38.0, "unit": "°C"}              # pas de seuil OMS, valeurs conservées
}

# (clé dans THRESHOLDS, colonne du DataFrame, libellé affiché)
POLLUTANTS = [
    ("pm2_5", "pm2_5", "PM2.5"),
    ("pm10", "pm10", "PM10"),
    ("no2", "nitrogen_dioxide", "NO2"),
    ("ozone", "ozone", "Ozone (O3)"),
    ("sulphur_dioxide", "sulphur_dioxide", "SO2"),
    ("carbon_monoxide", "carbon_monoxide", "CO"),
    ("us_aqi", "us_aqi", "Indice US AQI"),
]


def _format_value(value: float, unit: str) -> str:
    return f"{value:.1f} {unit}".strip()


def detect_alerts(df: pd.DataFrame) -> List[Dict[str, str]]:
    # Analyse les données récentes pour détecter les dépassements de seuils.
    alerts = []
    if df.empty:
        return alerts

    latest = df.iloc[-1]

    # Polluants (PM2.5, PM10, NO2, O3, SO2, CO, US AQI)
    for key, column, label in POLLUTANTS:
        if column not in df.columns or pd.isna(latest[column]):
            continue

        value = latest[column]
        threshold = THRESHOLDS[key]
        unit = threshold["unit"]

        if value >= threshold["danger"]:
            alerts.append({
                "level": "danger",
                "message": (
                    f"Alerte Rouge Pollution ({label}) : {_format_value(value, unit)} "
                    f"(Seuil: {threshold['danger']})"
                ),
            })
        elif value >= threshold["warning"]:
            alerts.append({
                "level": "warning",
                "message": (
                    f"Vigilance Pollution ({label}) : {_format_value(value, unit)} "
                    f"(Seuil: {threshold['warning']})"
                ),
            })

    # Température
    if "temperature_2m" in df.columns and not pd.isna(latest["temperature_2m"]):
        temp = latest["temperature_2m"]
        threshold = THRESHOLDS["temp_max"]

        if temp >= threshold["danger"]:
            alerts.append({
                "level": "danger",
                "message": f"Alerte Rouge Canicule : {_format_value(temp, threshold['unit'])}",
            })
        elif temp >= threshold["warning"]:
            alerts.append({
                "level": "warning",
                "message": f"Vigilance Forte Chaleur : {_format_value(temp, threshold['unit'])}",
            })

    return alerts
