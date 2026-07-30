output "artifact_repository" { value = google_artifact_registry_repository.images.name }
output "runtime_service_account" { value = google_service_account.runtime.email }
output "evidence_bucket" { value = google_storage_bucket.evidence.name }
output "bigquery_dataset" { value = "${var.project_id}.${google_bigquery_dataset.repo_health.dataset_id}" }
output "cloud_run_job" { value = google_cloud_run_v2_job.repo_health.name }
