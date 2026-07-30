from __future__ import annotations

import json
from typing import Any, Mapping

from ...run_bundle import DuplicateRunError, canonical_json, sha256_hex, validate_run_bundle


class GCSRunEvidenceSink:
    """Write a run packet once; the manifest is the completion marker."""

    def __init__(self, client: Any, bucket_name: str, *, prefix: str = "repo-health/runs") -> None:
        self.bucket = client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def write(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]:
        validate_run_bundle(bundle)
        payload = canonical_json(bundle)
        run_id = str(bundle["run"]["run_id"])
        base = f"{self.prefix}/{run_id}"
        bundle_name = f"{base}/run_bundle.json"
        manifest_name = f"{base}/manifest.json"
        digest = sha256_hex(payload)
        manifest = canonical_json({
            "schema_version": "repo_health.run_manifest.v1", "run_id": run_id,
            "files": {"run_bundle.json": {"sha256": digest, "bytes": len(payload)}},
        })
        bundle_status = self._create_or_verify(bundle_name, payload, "application/json")
        manifest_status = self._create_or_verify(manifest_name, manifest, "application/json")
        status = "duplicate" if bundle_status == manifest_status == "duplicate" else "created"
        return {"status": status, "run_id": run_id, "uri": f"gs://{self.bucket.name}/{base}/", "sha256": digest}

    def _create_or_verify(self, name: str, payload: bytes, content_type: str) -> str:
        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(payload, content_type=content_type, if_generation_match=0)
            return "created"
        except Exception as exc:
            try:
                existing = blob.download_as_bytes()
            except Exception:
                raise exc
            if existing != payload:
                raise DuplicateRunError(f"immutable GCS object {name!r} already contains different bytes") from exc
            return "duplicate"
