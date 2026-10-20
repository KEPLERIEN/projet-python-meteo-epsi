from typing import Dict, Any, Optional

import pandas as pd
import numpy as np


class DataProcessor:
    """
    Data Transformation and Calculations.
    Author: Student B (Data Analyst)
    """

    @staticmethod
    def process_raw_api_data(raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Transforms raw API responses into a clean Pandas DataFrame."""
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
        """
        Calculates a custom composite Comfort/Health Score (0-100 scale).
        Higher is better.
        """
        temp = df["temperature_2m"]
        humidity = df["relativehumidity_2m"]
        pm2_5 = df["pm2_5"]

        # Penalty factors based on optimal comfort conditions
        temp_penalty = np.abs(temp - 21.0) * 1.5
        humidity_penalty = np.abs(humidity - 50.0) * 0.3
        pollution_penalty = pm2_5 * 1.2

        score = 100 - (temp_penalty + humidity_penalty + pollution_penalty)
        return score.clip(0, 100).round(1)

    @staticmethod
    def filter_last_24_hours(
        df: pd.DataFrame,
        now: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """Return only rows from the previous 24 hours, excluding forecast data."""
        if df.empty:
            return df.copy()

        current_time = pd.Timestamp.now() if now is None else pd.Timestamp(now)
        timestamps = pd.to_datetime(df["datetime"], errors="coerce")
        start_time = current_time - pd.Timedelta(hours=24)
        mask = timestamps.between(start_time, current_time, inclusive="both")
        return df.loc[mask].copy()
