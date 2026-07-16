variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_account_id" {
  type = string
}

variable "github_token" {
  type      = string
  sensitive = true
}

variable "github_username" {
  type = string
}

variable "github_repo_name" {
  type = string
}

# --- GCP / Cloud Run ---

variable "gcp_project_id" {
  type        = string
  description = "GCP project ID to deploy the Cloud Run backend into (billing must be enabled)."
}

variable "gcp_region" {
  type        = string
  description = "GCP region for Cloud Run + Artifact Registry. us-central1 is a free-tier region."
  default     = "us-central1"
}

# Cloudflare Pages origin allowed by the backend CORS policy (CORS_ORIGINS env
# on Cloud Run). Change this if the Pages project uses a custom domain.
variable "frontend_origin" {
  type    = string
  default = "https://market-research.pages.dev"
}
