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
