import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_processing import DataProcessor
from src.alerts import detect_alerts


class TestDashboardModules(unittest.TestCase):
    """
    Unit testing module for verifying data processing & scoring logic.
    """

    def setUp(self):
        self.mock_df = pd.DataFrame({
            "time": ["2026-01-01T00:00", "2026-01-01T01:00"],
            "temperature_2m": [21.0, 40.0],
            "relativehumidity_2m": [50.0, 20.0],
            "pm2_5": [10.0, 30.0],
            "pm10": [20.0, 55.0],
            "nitrogen_dioxide": [15.0, 60.0]
        })

    def test_health_index_calculation(self):
        scores = DataProcessor.calculate_custom_health_index(self.mock_df)
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores.iloc[0], scores.iloc[1])

    def test_alerts_detection(self):
        alerts = detect_alerts(self.mock_df)
        self.assertTrue(len(alerts) > 0)

    def test_filter_last_24_hours_excludes_old_and_future_rows(self):
        now = pd.Timestamp("2026-10-20 12:30:00")
        df = pd.DataFrame({
            "datetime": pd.to_datetime([
                "2026-10-19 12:00:00",
                "2026-10-19 13:00:00",
                "2026-10-20 12:00:00",
                "2026-10-20 13:00:00",
            ]),
            "pm2_5": [1.0, 2.0, 3.0, 4.0],
        })

        result = DataProcessor.filter_last_24_hours(df, now=now)

        self.assertEqual(
            result["datetime"].tolist(),
            [pd.Timestamp("2026-10-19 13:00:00"), pd.Timestamp("2026-10-20 12:00:00")],
        )

    def test_select_current_observation_excludes_forecast_rows(self):
        df = pd.DataFrame({
            "datetime": pd.to_datetime([
                "2026-10-20 13:00:00",
                "2026-10-20 14:00:00",
                "2026-10-20 15:00:00",
                "2026-10-20 16:00:00",
            ]),
            "temperature_2m": [10.0, 12.0, 14.0, 16.0],
        })

        result = DataProcessor.select_current_observation(
            df,
            "2026-10-20T15:08",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["temperature_2m"], 14.0)


if __name__ == "__main__":
    unittest.main()
