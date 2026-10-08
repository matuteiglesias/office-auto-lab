from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from office_runtime.editorial.publisher.xurl_adapter import XurlAdapter


class XurlAdapterTests(unittest.TestCase):
    def test_configured_binary_is_used_without_contacting_x(self) -> None:
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"data":{"username":"ModernAIDev","id":"1927563136636243968"}}'})()
        with patch.dict(os.environ, {"XURL_BIN": "/home/matias/.n/bin/xurl"}), patch(
            "office_runtime.editorial.publisher.xurl_adapter.subprocess.run", return_value=completed
        ) as run:
            identity = XurlAdapter().whoami()

        self.assertEqual(identity.username, "ModernAIDev")
        self.assertEqual(identity.user_id, "1927563136636243968")
        self.assertEqual(
            run.call_args.args[0],
            ["/home/matias/.n/bin/xurl", "--app", "modernai-editorial", "--auth", "oauth1", "whoami"],
        )


if __name__ == "__main__":
    unittest.main()
