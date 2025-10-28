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

    service_labels = {
      location     = var.region
      service_name = var.run_service
    }
  }

  user_labels = {
    environment = "production"
  }
}

# 可用性SLO
resource "google_monitoring_slo" "availability_99" {
  service      = google_monitoring_service.run.service_id
  display_name = "99% - 可用性・暦月"

  goal            = 0.99
  calendar_period = "MONTH"

  request_based_sli {
    good_total_ratio {
      good_service_filter  = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.\"response_code_class\"=\"2xx\""
      total_service_filter = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\""
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
      duration = "300s"
      query = <<-EOT
fetch slo("${google_monitoring_slo.availability_99.name}")
| condition val() > 10
EOT
    }
  }

  notification_channels = [
    "projects/horse-nft-lab-clean/notificationChannels/11270000737687826943"
  ]

  enabled = true
}
