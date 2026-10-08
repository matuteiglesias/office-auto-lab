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
    _gh_variable_upsert,
)


class ActionsSetupDiagnosticsTests(unittest.TestCase):
    def test_disabled_github_variables_do_not_require_x_secrets(self):
        with patch("office_runtime.scripts.editorial_econ_actions_setup._gh_variable_upsert") as call:
            _configure_disabled_variables()
        self.assertEqual(call.call_count, len(DISABLED_VARIABLES))
        for args in call.call_args_list:
            self.assertIn(args.args[0], DISABLED_VARIABLES)
            self.assertEqual(args.args[1], DISABLED_VARIABLES[args.args[0]])

    def test_older_gh_rest_creates_missing_repo_variable(self):
        not_found = subprocess.CompletedProcess(
            args=["gh", "api"], returncode=1, stdout="",
            stderr="gh: Not Found (HTTP 404)",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=not_found), \
             patch("office_runtime.scripts.editorial_econ_actions_setup._command") as command:
            _gh_variable_upsert("EDITORIAL_ECON_SCHEDULER_ENABLED", "false")
        argv = command.call_args.args[0]
        self.assertEqual(argv[:4], ["gh", "api", "-X", "POST"])
        self.assertIn("value=false", argv)

    def test_older_gh_rest_updates_existing_repo_variable(self):
        exists = subprocess.CompletedProcess(args=["gh", "api"], returncode=0, stdout='{"name":"test"}', stderr="")
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=exists), \
             patch("office_runtime.scripts.editorial_econ_actions_setup._command") as command:
            _gh_variable_upsert("EDITORIAL_ECON_SCHEDULER_ENABLED", "false")
        argv = command.call_args.args[0]
        self.assertEqual(argv[:4], ["gh", "api", "-X", "PATCH"])
        self.assertIn("value=false", argv)

    def test_403_does_not_create_or_overwrite_variable(self):
        forbidden = subprocess.CompletedProcess(
            args=["gh", "api"], returncode=1, stdout="",
            stderr="gh: Resource not accessible by integration (HTTP 403)",
        )
        with patch("office_runtime.scripts.editorial_econ_actions_setup.subprocess.run", return_value=forbidden), \
             patch("office_runtime.scripts.editorial_econ_actions_setup._command") as command:
            with self.assertRaises(BootstrapBlocked):
                _gh_variable_upsert("EDITORIAL_ECON_SCHEDULER_ENABLED", "false")
        command.assert_not_called()

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
