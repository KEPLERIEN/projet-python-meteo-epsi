import unittest

import pandas as pd

from src.dashboard import build_csv_export, build_pdf_report


class TestDashboardExports(unittest.TestCase):
    def setUp(self):
        self.latest = pd.Series({
            "datetime": pd.Timestamp("2026-10-20 12:00"),
            "temperature_2m": 21.5,
            "relativehumidity_2m": 50,
            "us_aqi": float("nan"),
            "pm2_5": 8.2,
            "health_score": 92.1,
        })

    def test_csv_export_contains_headers_and_utf8_bom(self):
        csv_data = build_csv_export(pd.DataFrame([self.latest]))

        self.assertTrue(csv_data.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"temperature_2m", csv_data)
        self.assertIn(b"us_aqi", csv_data)

    def test_pdf_export_generates_valid_pdf_with_missing_aqi(self):
        pdf_data = build_pdf_report("Paris", self.latest, [])

        self.assertTrue(pdf_data.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
