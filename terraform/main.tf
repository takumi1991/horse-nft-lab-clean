terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.35" # 5.x 系ならOK
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------
# Service Monitoring に Cloud Run サービスを登録
# （ここで “サービス” オブジェクトを作る）
# ------------------------------------------------------------
resource "google_monitoring_service" "run" {
  service_id   = var.run_service          # 例: "horse-nft-lab-clean"
  display_name = var.run_service

  cloud_run {
    service  = var.run_service            # Cloud Run のサービス名
    location = var.region                 # 例: "asia-northeast1"
  }
}

# ------------------------------------------------------------
# SLO（= SLI を内包）
# 可用性 99% / ローリング30日
# リクエストベースで 「成功(2xx) / 全体」 比率を測定
# ------------------------------------------------------------
resource "google_monitoring_slo" "availability_99" {
  service               = google_monitoring_service.run.name  # projects/…/services/… の完全名
  slo_id                = "availability-99"
  display_name          = "Availability 99%"
  goal                  = 0.99
  rolling_period_days   = 30

  request_based_sli {
    good_total_ratio {
      # 全リクエスト
      total_service_filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_count\"",
        "resource.type=\"cloud_run_revision\"",
        "resource.label.\"service_name\"=\"${var.run_service}\"",
        "resource.label.\"location\"=\"${var.region}\""
      ])

      # 成功リクエスト（2xx）
      good_service_filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/request_count\"",
        "resource.type=\"cloud_run_revision\"",
        "resource.label.\"service_name\"=\"${var.run_service}\"",
        "resource.label.\"location\"=\"${var.region}\"",
        "metric.label.\"response_code_class\"=\"2xx\""
      ])
    }
  }
}

# ------------------------------------------------------------
# （オプション）SLOバーンレートのアラート骨子
# すでに Slack 連携済みなら notification_channels に ID を入れるだけで動作
# ※MQL はコンソールの「ポリシー > 条件 > View MQL」から
#   実環境のクエリを貼るのが最も確実です。
# ------------------------------------------------------------
# resource "google_monitoring_alert_policy" "slo_burnrate" {
#   display_name          = "SLO Burn rate - Availability 99%"
#   combiner              = "OR"
#   notification_channels = var.slack_channel_id != "" ? [var.slack_channel_id] : []
#
#   conditions {
#     display_name = "Burn rate > 10 over 60m"
#     condition_monitoring_query_language {
#       # ★ここに実環境でコピーした MQL を貼り付けるのが確実
#       # 参考：コンソールで作成した SLO アラート画面 > 条件 > View MQL
#       query = <<-EOT
#         # MQL の例（実環境に合わせて置換）
#         fetch monitoring_slo
#         | filter resource.service == "${google_monitoring_service.run.name}"
#         | filter resource.slo_id  == "${google_monitoring_slo.availability_99.slo_id}"
#         | within 60m
#         | group_by [], [ burn_rate:
#             ratio(sum(metric.slo_error_count), sum(metric.slo_request_count))]
#         | condition burn_rate > 10
#       EOT
#     }
#   }
# }
