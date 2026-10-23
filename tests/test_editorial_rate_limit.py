"""Offline regression for bounded editorial model RPM handling."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from office_runtime.editorial.producer import (
    EditorialProducerError, _model_pacing_seconds, _rate_limited,
)


class RateLimitTests(unittest.TestCase):
    def test_pacing_explicit_and_bounded(self):
        for value in ("0", "10", "30"):
            with self.subTest(value=value), patch.dict("os.environ", {"EDITORIAL_MODEL_PACE_SECONDS": value}):
                self.assertEqual(_model_pacing_seconds(), int(value))
        for value in ("-1", "31", "NaN"):
            with self.subTest(value=value), patch.dict("os.environ", {"EDITORIAL_MODEL_PACE_SECONDS": value}):
                with self.assertRaises(EditorialProducerError):
                    _model_pacing_seconds()

    def test_only_quota_errors_trigger_retry(self):
        class RateException(Exception):
            status_code = 429
        self.assertTrue(_rate_limited(RateException("quota")))
        self.assertTrue(_rate_limited(RuntimeError("RESOURCE_EXHAUSTED")))
        self.assertFalse(_rate_limited(ValueError("invalid schema")))
        self.assertFalse(_rate_limited(RuntimeError("service outage")))


if __name__ == "__main__":
    unittest.main()
