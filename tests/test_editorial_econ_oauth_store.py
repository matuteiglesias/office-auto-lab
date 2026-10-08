from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from office_runtime.scripts import editorial_econ_oauth_store as store


AUTH = b"""apps:
  argentina-econ-editorial:
    client_id: test-client
    client_secret: test-client-secret
    oauth2_tokens:
      matuteiglesias:
        refresh_token: refresh-v1
        access_token: access-v1
"""


class FakeBlob:
    def __init__(self, data: bytes = AUTH, generation: int = 7) -> None:
        self.data = data
        self.generation = generation
        self.uploads: list[tuple[bytes, int | None]] = []

    def reload(self) -> None:
        return None

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        if if_generation_match != self.generation:
            raise RuntimeError("generation conflict")
        return self.data

    def upload_from_string(self, data: bytes, *, content_type: str, if_generation_match: int) -> None:
        if if_generation_match != self.generation:
            raise RuntimeError("generation conflict")
        self.uploads.append((data, if_generation_match))
        self.data = data
        self.generation += 1


class EconomicsOAuthStoreTests(unittest.TestCase):
    def test_restore_refresh_persist_uses_generation_precondition(self) -> None:
        blob = FakeBlob()
        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"HOME": home}, clear=False), patch.object(store, "_blob", return_value=blob):
                store.restore()
                auth_path = Path(home) / ".xurl/auth.yml"
                state_path = Path(home) / ".xurl/.econ-gcs-state.json"
                self.assertEqual(auth_path.read_bytes(), AUTH)
                self.assertEqual(json.loads(state_path.read_text())["generation"], 7)

                refreshed = AUTH.replace(b"refresh-v1", b"refresh-v2").replace(b"access-v1", b"access-v2")
                auth_path.write_bytes(refreshed)
                store.persist()

                self.assertEqual(blob.uploads, [(refreshed, 7)])
                # A second persist in the same runner still uses the original
                # state, so a stale local state cannot overwrite a newer gen.
                with self.assertRaises(RuntimeError):
                    store.persist()

    def test_generation_conflict_fails_closed_and_fresh_runner_recovers(self) -> None:
        blob = FakeBlob()
        with tempfile.TemporaryDirectory() as first_home, patch.dict(os.environ, {"HOME": first_home}, clear=False), patch.object(store, "_blob", return_value=blob):
            store.restore()
            auth_path = Path(first_home) / ".xurl/auth.yml"
            auth_path.write_bytes(AUTH.replace(b"access-v1", b"access-v2"))
            blob.generation = 8
            with self.assertRaises(RuntimeError):
                store.persist()

        # A fresh runner does not reuse the stale local generation and can
        # restore the authoritative object after the operator resolves the
        # conflict.
        with tempfile.TemporaryDirectory() as second_home, patch.dict(os.environ, {"HOME": second_home}, clear=False), patch.object(store, "_blob", return_value=blob):
            blob.data = AUTH.replace(b"access-v1", b"access-v3")
            store.restore()
            self.assertEqual((Path(second_home) / ".xurl/auth.yml").read_bytes(), blob.data)


if __name__ == "__main__":
    unittest.main()
