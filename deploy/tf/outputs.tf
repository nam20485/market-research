output "cloud_run_url" {
  description = "Public HTTPS URL of the Cloud Run backend service."
  value       = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repo path (push images as <path>/<image>:<tag>)."
  value       = local.artifact_registry_image
}
