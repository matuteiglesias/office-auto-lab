"""No-secret regression cases for interactive economics bootstrap diagnostics."""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from office_runtime.scripts.editorial_econ_actions_setup import (
    BootstrapBlocked,
    DISABLED_VARIABLES,
    _command,
    _configure_disabled_variables,
)


class ActionsSetupDiagnosticsTests(unittest.TestCase):
    def test_disabled_github_variables_do_not_require_x_secrets(self):
        with patch("office_runtime.scripts.editorial_econ_actions_setup._command") as call:
            _configure_disabled_variables()
        self.assertEqual(call.call_count, len(DISABLED_VARIABLES))
        for args in call.call_args_list:
            argv = args.args[0]
            self.assertEqual(argv[:3], ["gh", "variable", "set"])
            self.assertIn("--repo", argv)
            self.assertNotIn("secret", " ".join(argv))

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

    def test_known_app_enrollment_error_is_not_labeled_bad_credentials(self):
        fake = subprocess.CompletedProcess(
            args=["xurl", "whoami"], returncode=1, stdout='{"detail":"client-not-enrolled","status":401}', stderr="",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=fake):
            with self.assertRaises(BootstrapBlocked) as err:
                _command(["xurl", "whoami"], stage="X_WHOAMI")
        self.assertIn("X_APP_NOT_ENROLLED_IN_API_PACKAGE", str(err.exception))

    def test_generic_401_does_not_assume_wrong_tokens(self):
        fake = subprocess.CompletedProcess(
            args=["xurl", "whoami"], returncode=1, stdout='{"status":401,"detail":"Unauthorized"}', stderr="",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=fake):
            with self.assertRaises(BootstrapBlocked) as err:
                _command(["xurl", "whoami"], stage="X_WHOAMI")
        self.assertIn("X_REJECTED_OAUTH1_CREDENTIALS_OR_APP_ACCESS", str(err.exception))

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
