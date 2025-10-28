provider "google" {
  project     = var.project_id != "" ? var.project_id : var.GOOGLE_PROJECT
  credentials = var.GOOGLE_CREDENTIALS
  region      = var.region
}

# --- SLO定義 ---
resource "google_monitoring_slo" "availability_99" {
  service      = "projects/${var.project_id}/services/${var.run_service}"
  display_name = "99% - 可用性・暦月"

  goal = 0.99
  rolling_period_days = null
  calendar_period     = "MONTH"

  request_based_sli {
    availability {
      enabled = true
    }
  }
}

# --- アラートポリシー定義 ---
resource "google_monitoring_alert_policy" "slo_burnrate_alert" {
  display_name = "SLO Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Burn rate above 10"
    condition_monitoring_query_language {
      query = <<EOT
fetch slo("projects/${var.project_id}/services/${var.run_service}/serviceLevelObjectives/${google_monitoring_slo.availability_99.name}")
| condition val() > 10
EOT
    }
  }

  notification_channels = [
    var.slack_channel_id != "" ? var.slack_channel_id : "projects/${var.project_id}/notificationChannels/YOUR_SLACK_CHANNEL_ID"
  ]

  enabled = true
}
