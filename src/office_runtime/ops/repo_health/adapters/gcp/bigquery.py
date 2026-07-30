from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping, Sequence

from ...run_bundle import DuplicateRunError, canonical_json, sha256_hex, validate_run_bundle


class GoogleBigQueryClient:
    """Small wrapper over google-cloud-bigquery; credentials come from ADC."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def lookup_run_sha(self, table: str, run_id: str, run_date: str) -> str | None:
        from google.cloud import bigquery

        config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("run_date", "DATE", date.fromisoformat(run_date)),
        ])
        rows = list(self.client.query(
            f"SELECT bundle_sha256 FROM `{table}` WHERE run_date = @run_date AND run_id = @run_id LIMIT 1",
            job_config=config,
        ).result())
        return str(rows[0]["bundle_sha256"]) if rows else None

    def insert_rows(self, table: str, rows: Sequence[Mapping[str, Any]], row_ids: Sequence[str]) -> None:
        from google.cloud import bigquery

        if len(rows) != len(row_ids):
            raise ValueError("BigQuery rows and row_ids must align")
        for row, row_id in zip(rows, row_ids):
            if row["row_id"] != row_id:
                raise ValueError("BigQuery row_id must be producer-owned and stable")
            columns = list(row)
            select = []
            parameters = []
            for column in columns:
                value = row[column]
                if column == "raw_json":
                    select.append("PARSE_JSON(@raw_json) AS raw_json")
                    parameters.append(bigquery.ScalarQueryParameter(column, "STRING", value))
                elif column == "run_date":
                    select.append("DATE(@run_date) AS run_date")
                    parameters.append(bigquery.ScalarQueryParameter(column, "STRING", value))
                elif column in {"started_at", "ended_at"}:
                    select.append(f"TIMESTAMP(@{column}) AS {column}")
                    parameters.append(bigquery.ScalarQueryParameter(column, "STRING", value))
                else:
                    select.append(f"@{column} AS {column}")
                    value_type = "INT64" if isinstance(value, int) else "STRING"
                    parameters.append(bigquery.ScalarQueryParameter(column, value_type, value))
            column_sql = ", ".join(columns)
            value_sql = ", ".join(f"S.{column}" for column in columns)
            query = f"""
MERGE `{table}` T
USING (SELECT {', '.join(select)}) S
ON T.row_id = S.row_id
WHEN MATCHED AND T.bundle_sha256 != S.bundle_sha256 THEN
  UPDATE SET raw_json = ERROR('conflicting producer row identity')
WHEN NOT MATCHED THEN
  INSERT ({column_sql}) VALUES ({value_sql})
"""
            config = bigquery.QueryJobConfig(query_parameters=parameters)
            self.client.query(query, job_config=config).result()


class BigQueryHistorySink:
    TABLES = ("runs", "run_intents", "plugin_results", "exceptions", "prepared_blocks")

    def __init__(self, client: Any, project_id: str, dataset: str = "repo_health") -> None:
        self.client = client
        self.dataset = f"{project_id}.{dataset}"

    def append(self, bundle: Mapping[str, Any]) -> Mapping[str, Any]:
        validate_run_bundle(bundle)
        run_id = str(bundle["run"]["run_id"])
        run_date = str(bundle["run"]["started_at"])[:10]
        digest = sha256_hex(canonical_json(bundle))
        existing = self.client.lookup_run_sha(f"{self.dataset}.runs", run_id, run_date)
        if existing:
            if existing == digest:
                return {"status": "duplicate", "run_id": run_id, "sha256": digest}
            raise DuplicateRunError(f"BigQuery run_id {run_id!r} has conflicting bundle_sha256")
        rows = self._rows(bundle, digest)
        # Detail rows first; the runs row is the completion/idempotency marker.
        for table in self.TABLES[1:]:
            values = rows[table]
            if values:
                self.client.insert_rows(f"{self.dataset}.{table}", values, [row["row_id"] for row in values])
        self.client.insert_rows(f"{self.dataset}.runs", rows["runs"], [run_id])
        return {"status": "appended", "run_id": run_id, "sha256": digest}

    def _rows(self, bundle: Mapping[str, Any], digest: str) -> dict[str, list[dict[str, Any]]]:
        run_id = str(bundle["run"]["run_id"])
        run = bundle["run"]
        common = {"run_id": run_id, "run_date": str(run["started_at"])[:10]}
        return {
            "runs": [{**common, "row_id": run_id, "status": run["status"], "attempt": run["attempt"],
                      "started_at": run["started_at"], "ended_at": run["ended_at"],
                      "producer_commit": bundle["source"]["producer_commit"], "policy_input_id": bundle["policy"]["input_id"],
                      "policy_sha256": bundle["policy"]["sha256"], "bundle_sha256": digest, "raw_json": json.dumps(bundle, sort_keys=True)}],
            "run_intents": [_raw_row(common, row["intent_id"], row, digest) for row in bundle["intents"]],
            "plugin_results": [_raw_row(common, row["result_id"], row, digest) for row in bundle["plugin_results"]],
            "exceptions": [_raw_row(common, row["exception_id"], row, digest) for row in bundle["exceptions"]],
            "prepared_blocks": [_raw_row(common, row["block_id"], row, digest) for row in bundle["prepared_blocks"]],
        }


def _raw_row(common: Mapping[str, Any], row_id: str, value: Mapping[str, Any], digest: str) -> dict[str, Any]:
    typed = {key: value[key] for key in ("project_id", "plugin", "normalized_class", "bucket", "category", "archetype", "mode") if key in value}
    return {**common, "row_id": row_id, "bundle_sha256": digest, **typed, "raw_json": json.dumps(value, sort_keys=True)}
