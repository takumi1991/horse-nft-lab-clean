provider "google" {
  project     = var.project_id
  credentials = var.GOOGLE_CREDENTIALS
  region      = var.region
}

# Cloud RunサービスをMonitoring上に登録
resource "google_monitoring_service" "run" {
  service_id   = var.run_service
  display_name = "Cloud Run Service - ${var.run_service}"

  basic_service {
    service_type = "CLOUD_RUN"
  }

  user_labels = {
    environment = "production"
  }
}

# 可用性SLO
resource "google_monitoring_slo" "availability_99" {
  service      = google_monitoring_service.run.name
  display_name = "99% - 可用性・暦月"

  goal            = 0.99
  calendar_period = "MONTH"

  request_based_sli {
    good_total_ratio {
      good_service_filter = <<EOT
metric.type="run.googleapis.com/request_count"
resource.type="cloud_run_revision"
metric.label.response_code_class="2xx"
EOT

      total_service_filter = <<EOT
metric.type="run.googleapis.com/request_count"
resource.type="cloud_run_revision"
EOT
    }
  }
}

# バーンレートアラート
resource "google_monitoring_alert_policy" "slo_burnrate_alert" {
  display_name = "SLO Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Burn rate above 10"
    condition_monitoring_query_language {
      duration = "900s"
      query = <<EOT
fetch slo("${google_monitoring_slo.availability_99.id}")
| condition val() > 10
EOT
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [
    "projects/${var.project_id}/notificationChannels/${var.slack_channel_id}"
  ]

  enabled = true
}
