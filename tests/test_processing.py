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


if __name__ == "__main__":
    unittest.main()
