variable "project_id" {
  type = string
}
variable "billing_account_id" {
  type        = string
  description = "Billing account used for the mandatory USD 10 monthly budget alert."
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "name_prefix" {
  type    = string
  default = "repo-health"
}
variable "image" {
  type        = string
  description = "Artifact Registry image pinned by digest."
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "image must be pinned with @sha256:<64 lowercase hex>."
  }
}
variable "source_commit" {
  type = string
  validation {
    condition     = length(trimspace(var.source_commit)) >= 7
    error_message = "source_commit must identify the image source."
  }
}
variable "policy_snapshot_json" {
  type        = string
  description = "Frozen, validated governance snapshot for the first bounded run."
  validation {
    condition     = can(jsondecode(var.policy_snapshot_json)) && length(var.policy_snapshot_json) <= 30000
    error_message = "policy_snapshot_json must be valid JSON no larger than 30KB."
  }
}
variable "dataset_id" {
  type    = string
  default = "repo_health"
}
variable "evidence_retention_days" {
  type    = number
  default = 30
}
variable "allow_destroy" {
  type        = bool
  default     = false
  description = "Explicit teardown switch; false protects evidence resources."
}
