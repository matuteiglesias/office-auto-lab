CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.repo_health`
OPTIONS(location = '${REGION}');

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.repo_health.runs` (
  row_id STRING NOT NULL, run_id STRING NOT NULL, run_date DATE NOT NULL, status STRING NOT NULL,
  attempt INT64 NOT NULL, started_at TIMESTAMP NOT NULL, ended_at TIMESTAMP NOT NULL,
  producer_commit STRING NOT NULL, policy_input_id STRING NOT NULL, policy_sha256 STRING NOT NULL,
  bundle_sha256 STRING NOT NULL, raw_json JSON NOT NULL
) PARTITION BY run_date CLUSTER BY status;

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.repo_health.run_intents`
(row_id STRING NOT NULL, run_id STRING NOT NULL, run_date DATE NOT NULL, bundle_sha256 STRING NOT NULL,
 project_id STRING NOT NULL, plugin STRING NOT NULL, raw_json JSON NOT NULL)
PARTITION BY run_date CLUSTER BY project_id, plugin;

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.repo_health.plugin_results`
(row_id STRING NOT NULL, run_id STRING NOT NULL, run_date DATE NOT NULL, bundle_sha256 STRING NOT NULL,
 project_id STRING NOT NULL, plugin STRING NOT NULL, normalized_class STRING NOT NULL, bucket STRING NOT NULL,
 raw_json JSON NOT NULL)
PARTITION BY run_date CLUSTER BY project_id, plugin, normalized_class;

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.repo_health.exceptions`
(row_id STRING NOT NULL, run_id STRING NOT NULL, run_date DATE NOT NULL, bundle_sha256 STRING NOT NULL,
 category STRING NOT NULL, raw_json JSON NOT NULL)
PARTITION BY run_date CLUSTER BY category;

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.repo_health.prepared_blocks`
(row_id STRING NOT NULL, run_id STRING NOT NULL, run_date DATE NOT NULL, bundle_sha256 STRING NOT NULL,
 archetype STRING, mode STRING, raw_json JSON NOT NULL)
PARTITION BY run_date CLUSTER BY archetype, mode;

CREATE OR REPLACE VIEW `${PROJECT_ID}.repo_health.latest_plugin_health` AS
SELECT * EXCEPT(row_number) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY project_id, plugin ORDER BY run_date DESC, run_id DESC) AS row_number
  FROM `${PROJECT_ID}.repo_health.plugin_results`
  WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
) WHERE row_number = 1;

CREATE OR REPLACE VIEW `${PROJECT_ID}.repo_health.unresolved_issue_signatures` AS
SELECT project_id, plugin, normalized_class, bucket, COUNT(*) AS observations, MIN(run_date) AS first_seen, MAX(run_date) AS last_seen
FROM `${PROJECT_ID}.repo_health.plugin_results`
WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  AND normalized_class IN ('system_error', 'actionable_failure', 'warning', 'ineligible')
GROUP BY project_id, plugin, normalized_class, bucket;

CREATE OR REPLACE VIEW `${PROJECT_ID}.repo_health.prepared_blocks_weekly` AS
SELECT DATE_TRUNC(run_date, WEEK) AS week, archetype, mode, COUNT(*) AS block_count
FROM `${PROJECT_ID}.repo_health.prepared_blocks`
WHERE run_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY week, archetype, mode;
