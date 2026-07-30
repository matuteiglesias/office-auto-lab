locals {
  services = toset([
    "artifactregistry.googleapis.com", "bigquery.googleapis.com", "run.googleapis.com",
    "storage.googleapis.com", "logging.googleapis.com", "monitoring.googleapis.com",
    "billingbudgets.googleapis.com"
  ])
  runtime_member = "serviceAccount:${google_service_account.runtime.email}"
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_billing_budget" "monthly" {
  billing_account = startswith(var.billing_account_id, "billingAccounts/") ? var.billing_account_id : "billingAccounts/${var.billing_account_id}"
  display_name    = "${var.name_prefix}-10-usd-monthly"
  amount {
    specified_amount {
      currency_code = "USD"
      units         = "10"
    }
  }
  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }
  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  depends_on = [google_project_service.required]
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.name_prefix
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = "${var.name_prefix}-runtime"
  display_name = "Repo Health Cloud Run Job runtime"
}

resource "google_storage_bucket" "evidence" {
  name                        = "${var.project_id}-${var.name_prefix}-evidence"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.allow_destroy
  lifecycle_rule {
    condition {
      age = var.evidence_retention_days
    }
    action {
      type = "Delete"
    }
  }
  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "create" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectCreator"
  member = local.runtime_member
}
resource "google_storage_bucket_iam_member" "read" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectViewer"
  member = local.runtime_member
}

resource "google_bigquery_dataset" "repo_health" {
  dataset_id                 = var.dataset_id
  location                   = var.region
  delete_contents_on_destroy = var.allow_destroy
  depends_on                 = [google_project_service.required]
}

locals {
  common_fields = [
    { name = "row_id", type = "STRING", mode = "REQUIRED" },
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "run_date", type = "DATE", mode = "REQUIRED" },
    { name = "bundle_sha256", type = "STRING", mode = "REQUIRED" },
  ]
  detail_schemas = {
    run_intents = concat(local.common_fields, [
      { name = "project_id", type = "STRING", mode = "REQUIRED" }, { name = "plugin", type = "STRING", mode = "REQUIRED" },
      { name = "raw_json", type = "JSON", mode = "REQUIRED" }
    ])
    plugin_results = concat(local.common_fields, [
      { name = "project_id", type = "STRING", mode = "REQUIRED" }, { name = "plugin", type = "STRING", mode = "REQUIRED" },
      { name = "normalized_class", type = "STRING", mode = "REQUIRED" }, { name = "bucket", type = "STRING", mode = "REQUIRED" },
      { name = "raw_json", type = "JSON", mode = "REQUIRED" }
    ])
    exceptions = concat(local.common_fields, [
      { name = "category", type = "STRING", mode = "REQUIRED" }, { name = "raw_json", type = "JSON", mode = "REQUIRED" }
    ])
    prepared_blocks = concat(local.common_fields, [
      { name = "archetype", type = "STRING", mode = "NULLABLE" }, { name = "mode", type = "STRING", mode = "NULLABLE" },
      { name = "raw_json", type = "JSON", mode = "REQUIRED" }
    ])
  }
}

resource "google_bigquery_table" "runs" {
  dataset_id          = google_bigquery_dataset.repo_health.dataset_id
  table_id            = "runs"
  deletion_protection = !var.allow_destroy
  time_partitioning {
    type  = "DAY"
    field = "run_date"
  }
  require_partition_filter = true
  clustering               = ["status"]
  schema = jsonencode(concat(local.common_fields, [
    { name = "status", type = "STRING", mode = "REQUIRED" }, { name = "attempt", type = "INTEGER", mode = "REQUIRED" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED" }, { name = "ended_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "producer_commit", type = "STRING", mode = "REQUIRED" }, { name = "policy_input_id", type = "STRING", mode = "REQUIRED" },
    { name = "policy_sha256", type = "STRING", mode = "REQUIRED" }, { name = "raw_json", type = "JSON", mode = "REQUIRED" }
  ]))
}

resource "google_bigquery_table" "details" {
  for_each            = local.detail_schemas
  dataset_id          = google_bigquery_dataset.repo_health.dataset_id
  table_id            = each.key
  deletion_protection = !var.allow_destroy
  time_partitioning {
    type  = "DAY"
    field = "run_date"
  }
  require_partition_filter = true
  schema                   = jsonencode(each.value)
}

resource "google_bigquery_table" "latest_plugin_health" {
  dataset_id = google_bigquery_dataset.repo_health.dataset_id
  table_id   = "latest_plugin_health"
  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT * EXCEPT(row_number) FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY project_id, plugin ORDER BY run_date DESC, run_id DESC) AS row_number
        FROM `${var.project_id}.${var.dataset_id}.plugin_results`
        WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
      ) WHERE row_number = 1
    SQL
  }
  depends_on = [google_bigquery_table.details]
}

resource "google_bigquery_table" "unresolved_issue_signatures" {
  dataset_id = google_bigquery_dataset.repo_health.dataset_id
  table_id   = "unresolved_issue_signatures"
  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT project_id, plugin, normalized_class, bucket, COUNT(*) AS observations,
             MIN(run_date) AS first_seen, MAX(run_date) AS last_seen
      FROM `${var.project_id}.${var.dataset_id}.plugin_results`
      WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND normalized_class IN ('system_error', 'actionable_failure', 'warning', 'ineligible')
      GROUP BY project_id, plugin, normalized_class, bucket
    SQL
  }
  depends_on = [google_bigquery_table.details]
}

resource "google_bigquery_table" "prepared_blocks_weekly" {
  dataset_id = google_bigquery_dataset.repo_health.dataset_id
  table_id   = "prepared_blocks_weekly"
  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT DATE_TRUNC(run_date, WEEK) AS week, archetype, mode, COUNT(*) AS block_count
      FROM `${var.project_id}.${var.dataset_id}.prepared_blocks`
      WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
      GROUP BY week, archetype, mode
    SQL
  }
  depends_on = [google_bigquery_table.details]
}

resource "google_bigquery_dataset_iam_member" "writer" {
  dataset_id = google_bigquery_dataset.repo_health.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = local.runtime_member
}
resource "google_project_iam_member" "job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.runtime_member
}
resource "google_project_iam_member" "logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = local.runtime_member
}

resource "google_logging_metric" "job_errors" {
  name   = "${var.name_prefix}-job-errors"
  filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${var.name_prefix}-remote\" AND severity>=ERROR"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "job_errors" {
  display_name = "${var.name_prefix} job errors"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run Job emitted an error"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.job_errors.name}\" AND resource.type=\"cloud_run_job\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}
resource "google_artifact_registry_repository_iam_member" "pull" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.reader"
  member     = local.runtime_member
}

resource "google_cloud_run_v2_job" "repo_health" {
  name                = "${var.name_prefix}-remote"
  location            = var.region
  deletion_protection = !var.allow_destroy
  lifecycle {
    precondition {
      condition     = startswith(var.image, "${var.region}-docker.pkg.dev/${var.project_id}/${var.name_prefix}/")
      error_message = "image must come from the Terraform-managed Artifact Registry repository."
    }
  }
  template {
    task_count = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 1
      containers {
        image = var.image
        args  = ["--profile", "gcp"]
        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "REPO_HEALTH_GCS_BUCKET"
          value = google_storage_bucket.evidence.name
        }
        env {
          name  = "REPO_HEALTH_BQ_DATASET"
          value = google_bigquery_dataset.repo_health.dataset_id
        }
        env {
          name  = "REPO_HEALTH_POLICY_JSON"
          value = var.policy_snapshot_json
        }
        env {
          name  = "SOURCE_COMMIT"
          value = var.source_commit
        }
      }
    }
  }
  depends_on = [
    google_project_service.required, google_storage_bucket_iam_member.create,
    google_storage_bucket_iam_member.read, google_bigquery_dataset_iam_member.writer,
    google_project_iam_member.job_user, google_project_iam_member.logs
  ]
}
