"""No-secret regression cases for interactive economics bootstrap diagnostics."""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from office_runtime.scripts.editorial_econ_actions_setup import (
    BootstrapBlocked,
    _command,
)


class ActionsSetupDiagnosticsTests(unittest.TestCase):
    def test_wrong_oauth_token_is_classified_without_stderr_leak(self):
        fake = subprocess.CompletedProcess(
            args=["xurl", "whoami"], returncode=1, stdout="",
            stderr="HTTP 401 token secret sensitive-value-should-not-appear",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=fake):
            with self.assertRaises(BootstrapBlocked) as err:
                _command(["xurl", "whoami"], stage="X_WHOAMI")
        self.assertIn("X_REJECTED_OAUTH1_CREDENTIALS", str(err.exception))
        self.assertNotIn("sensitive-value-should-not-appear", str(err.exception))

    def test_missing_xurl_token_reports_specific_safe_code(self):
        fake = subprocess.CompletedProcess(
            args=["xurl", "whoami"], returncode=1, stdout="",
            stderr="TokenNotFound: OAuth1 token not found",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=fake):
            with self.assertRaises(BootstrapBlocked) as err:
                _command(["xurl", "whoami"], stage="X_WHOAMI")
        self.assertIn("NO_OAUTH1_TOKEN_LOADED", str(err.exception))

    def test_gh_stage_reports_which_operation_failed(self):
        fake = subprocess.CompletedProcess(
            args=["gh", "secret", "set"], returncode=1, stdout="",
            stderr="token=hidden-value",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=fake):
            with self.assertRaises(BootstrapBlocked) as err:
                _command(["gh", "secret", "set"], input_data="secret", stage="GITHUB_SECRET")
        self.assertIn("GITHUB_SECRET", str(err.exception))
        self.assertNotIn("hidden-value", str(err.exception))


if __name__ == "__main__":
    unittest.main()
