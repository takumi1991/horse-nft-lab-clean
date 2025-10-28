output "monitoring_service_name" {
  value       = google_monitoring_service.run.name
  description = "Full name of Monitoring Service (projects/.../services/...)"
}

output "slo_name" {
  value       = google_monitoring_slo.availability_99.name
  description = "Full name of SLO (projects/.../services/.../serviceLevelObjectives/...)"
}
