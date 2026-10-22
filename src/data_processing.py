from typing import Dict, Any, Optional

import pandas as pd
import numpy as np


class DataProcessor:
    """Transformation et calculs sur les données."""

    @staticmethod
    def process_raw_api_data(raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Transforme les réponses API brutes en DataFrame Pandas propre."""
        w_hourly = raw_data.get("weather", {}).get("hourly", {})
        a_hourly = raw_data.get("air_quality", {}).get("hourly", {})

        df_weather = pd.DataFrame(w_hourly)
        df_air = pd.DataFrame(a_hourly)

        if df_weather.empty or df_air.empty:
            return pd.DataFrame()

        df = pd.merge(df_weather, df_air, on="time", how="inner")
        df["datetime"] = pd.to_datetime(df["time"])
        df.sort_values("datetime", inplace=True)
        return df

    @staticmethod
    def calculate_custom_health_index(df: pd.DataFrame) -> pd.Series:
        """Calcule un score de confort/santé (0-100)."""
        temp = df["temperature_2m"]
        humidity = df["relativehumidity_2m"]
        pm2_5 = df["pm2_5"]

        # Facteurs de pénalité basés sur le confort optimal
        temp_penalty = np.abs(temp - 21.0) * 1.5
        humidity_penalty = np.abs(humidity - 50.0) * 0.3
        pollution_penalty = pm2_5 * 1.2

        score = 100 - (temp_penalty + humidity_penalty + pollution_penalty)
        return score.clip(0, 100).round(1)

    @staticmethod
    def filter_last_24_hours(df: pd.DataFrame, now: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """Retourne les mesures des 24 dernières heures (hors prévisions)."""
        if df.empty:
            return df.copy()

        current_time = pd.Timestamp.now() if now is None else pd.Timestamp(now)
        timestamps = pd.to_datetime(df["datetime"], errors="coerce")
        start_time = current_time - pd.Timedelta(hours=24)
        mask = timestamps.between(start_time, current_time, inclusive="both")
        return df.loc[mask].copy()

    @staticmethod
    def select_current_observation(df: pd.DataFrame, observation_time: Optional[str]) -> pd.DataFrame:
        """Sélectionne la ligne la plus proche de l'heure actuelle."""
        if df.empty:
            return df.copy()

        if not observation_time:
            return df.iloc[[-1]].copy()

        reference_time = pd.to_datetime(observation_time, errors="coerce")
        if pd.isna(reference_time):
            return df.iloc[[-1]].copy()

        timestamps = pd.to_datetime(df["datetime"], errors="coerce")
        current_rows = df.loc[timestamps <= reference_time]
        if current_rows.empty:
            return df.iloc[[timestamps.sub(reference_time).abs().argmin()]].copy()
        return current_rows.iloc[[-1]].copy()
