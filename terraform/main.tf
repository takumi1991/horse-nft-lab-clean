provider "google" {
  project     = var.project_id
  credentials = var.GOOGLE_CREDENTIALS
  region      = var.region
}

resource "google_monitoring_service" "run" {
  service_id   = var.run_service
  display_name = "Cloud Run Service - ${var.run_service}"

  user_labels = {
    environment = "production"
  }
}

resource "google_monitoring_slo" "availability_99" {
  service      = google_monitoring_service.run.name
  display_name = "99% - 可用性・暦月"

  goal                = 0.99
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
fetch slo("${google_monitoring_slo.availability_99.id}")
| condition val() > 10
EOT
    }
  }

  notification_channels = [
    "projects/${var.project_id}/notificationChannels/${var.slack_channel_id}"
  ]

  enabled = true
}
