resource "google_monitoring_slo" "availability_99" {
  service      = "projects/horse-nft-lab-clean/services/horse-nft-lab-clean"
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


resource "google_monitoring_alert_policy" "slo_burnrate_alert" {
  display_name = "SLO Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Burn rate above 10"
    condition_monitoring_query_language {
      query = <<EOT
fetch slo("projects/horse-nft-lab-clean/services/horse-nft-lab-clean/serviceLevelObjectives/${google_monitoring_slo.availability_99.id}")
| condition val() > 10
EOT
    }
  }

  notification_channels = [
    "projects/horse-nft-lab-clean/notificationChannels/YOUR_SLACK_CHANNEL_ID"
  ]

  enabled = true
}


provider "google" {
  project     = var.project_id
  credentials = var.GOOGLE_CREDENTIALS
  region      = "asia-northeast1"
}
