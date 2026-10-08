"""Fixture-only credential contract; never use real tokens in CI."""
from __future__ import annotations

import unittest

from office_runtime.scripts.editorial_econ_oauth1_secret import validate


def fixture(*, app="argentina-econ-editorial", kind="oauth1", include_dev=False):
    content = {
        "default_app": "argentina-econ-editorial",
        "apps": {
            app: {
                "oauth1_token": {
                    "type": kind,
                    "oauth1": {
                        "access_token": "fixture_access_not_real",
                        "token_secret": "fixture_token_secret_not_real",
                        "consumer_key": "fixture_consumer_not_real",
                        "consumer_secret": "fixture_consumer_secret_not_real",
                    },
                },
            }
        },
    }
    if include_dev:
        content["apps"]["modernai-editorial"] = {}
    import yaml
    return yaml.safe_dump(content)


class EconomicsOAuth1OnlyTests(unittest.TestCase):
    def test_valid_one_app_static_token(self):
        self.assertEqual(list(validate(fixture())["apps"]), ["argentina-econ-editorial"])

    def test_reject_developer_app(self):
        with self.assertRaises(ValueError):
            validate(fixture(include_dev=True))

    def test_reject_misnamed_app(self):
        with self.assertRaises(ValueError):
            validate(fixture(app="another-app"))

    def test_reject_wrong_token_kind(self):
        with self.assertRaises(ValueError):
            validate(fixture(kind="oauth2"))

    def test_reject_absent_consumer_secret(self):
        import yaml
        data = yaml.safe_load(fixture())
        data["apps"]["argentina-econ-editorial"]["oauth1_token"]["oauth1"]["consumer_secret"] = ""
        with self.assertRaises(ValueError):
            validate(yaml.safe_dump(data))

    def test_reject_oauth2_material(self):
        import yaml
        data = yaml.safe_load(fixture())
        data["apps"]["argentina-econ-editorial"]["oauth2_tokens"] = {"matuteiglesias": {"refresh_token": "dummy"}}
        with self.assertRaises(ValueError):
            validate(yaml.safe_dump(data))


if __name__ == "__main__":
    unittest.main()
