variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "Region of Cloud Run service (e.g. asia-northeast1)"
  type        = string
  default     = "asia-northeast1"
}

variable "run_service" {
  description = "Cloud Run service name (e.g. horse-nft-lab-clean)"
  type        = string
}

# 既存の Slack 通知チャネル ID（作っていればここに入れる）
# 例: projects/XXXX/notificationChannels/NNNNN
variable "slack_channel_id" {
  description = "Existing Monitoring Notification Channel ID for Slack"
  type        = string
  default     = ""
}

# Terraform Cloud の Variable で渡す GOOGLE_PROJECT と GOOGLE_CREDENTIALS を受け取るため
variable "GOOGLE_PROJECT" {
  description = "Alias for Terraform Cloud variable (same as project_id)"
  type        = string
  default     = ""
}

variable "GOOGLE_CREDENTIALS" {
  description = "Base64-encoded GCP service account key (Sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}
