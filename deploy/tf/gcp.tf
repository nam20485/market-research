# Google Cloud Run backend + supporting infra.
#
# This file provisions everything needed to run the FastAPI backend on Cloud
# Run (scale-to-zero, free tier) and to let a keyed GitHub Actions workflow
# build/push images and deploy. Secret *values* are intentionally NOT managed
# here (see google_secret_manager_secret below) so they never land in tfstate.
#
# All deploys stay manual: this config only creates infrastructure. The image
# is owned by CI (see lifecycle ignore_changes on the Cloud Run container).

# App secrets exposed to the container as env vars. Only the secret *containers*
# and IAM are created by Terraform; the values are added out-of-band via
# `gcloud secrets versions add` (see the report / README) so they stay out of
# tfstate.
locals {
  app_secret_ids = [
    "LLM_API_KEY",
    "VISION_API_KEY",
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "ZAI_API_KEY",
  ]
  cloud_run_service_name  = "market-research-backend"
  artifact_repository_id  = "market-research"
  artifact_registry_image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

# --- Enable required APIs -----------------------------------------------------

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  service = each.value

  # Keep APIs enabled on `terraform destroy` — disabling them can affect other
  # resources in the project and is rarely what you want.
  disable_on_destroy = false
}

# --- Artifact Registry (Docker) ----------------------------------------------

resource "google_artifact_registry_repository" "backend" {
  location      = var.gcp_region
  repository_id = local.artifact_repository_id
  description   = "Docker images for the market-research backend (Cloud Run)."
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

# --- Deploy service account (used by GitHub Actions via key) ------------------

resource "google_service_account" "deploy" {
  account_id   = "market-research-deploy"
  display_name = "market-research CI deploy SA"

  depends_on = [google_project_service.required]
}

# JSON key for the deploy SA. `private_key` is base64-encoded JSON; it is pushed
# to GitHub as the GCP_SA_KEY secret (decoded) below. This lands in tfstate, so
# keep tfstate gitignored/encrypted and rotate the key periodically.
resource "google_service_account_key" "deploy" {
  service_account_id = google_service_account.deploy.name
}

# Deploy SA can deploy Cloud Run services and push images.
resource "google_project_iam_member" "deploy_run_developer" {
  project = var.gcp_project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_artifactregistry_writer" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Deploy SA must be able to act as the runtime SA to deploy a service that runs
# as it (roles/iam.serviceAccountUser on the runtime SA).
resource "google_service_account_iam_member" "deploy_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# --- Runtime service account (identity of the Cloud Run service) --------------

resource "google_service_account" "runtime" {
  account_id   = "market-research-runtime"
  display_name = "market-research Cloud Run runtime SA"

  depends_on = [google_project_service.required]
}

# --- Secret Manager containers (values added out-of-band) ---------------------

# Containers only — NO secret versions/values here on purpose. Populate each
# with: gcloud secrets versions add <SECRET_ID> --data-file=- <<< "value"
resource "google_secret_manager_secret" "app" {
  for_each = toset(local.app_secret_ids)

  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

# Runtime SA can read each secret's value at container start.
resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each = google_secret_manager_secret.app

  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run service --------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = local.cloud_run_service_name
  location = var.gcp_region

  # Let manual `terraform destroy` remove the service without an extra flag.
  deletion_protection = false

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      # Placeholder image only. CI builds and deploys the real image (SHA
      # tagged) into Artifact Registry, so Terraform must not fight it.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8000
      }

      env {
        name  = "CORS_ORIGINS"
        value = var.frontend_origin
      }

      dynamic "env" {
        for_each = google_secret_manager_secret.app
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runtime_accessor,
  ]
}

# Public API: allow unauthenticated invocations from the browser.
# NOTE: an organization policy (e.g. iam.allowedPolicyMemberDomains /
# constraints/iam.allowedPolicyMemberDomains) may block `allUsers`. On such
# accounts, front the service differently or grant a specific principal.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Wire the deploy key + backend URL into GitHub Actions --------------------

# `private_key` is base64-encoded JSON; decode it so the secret holds raw JSON,
# matching google-github-actions/auth's `credentials_json` expectation.
resource "github_actions_secret" "gcp_sa_key" {
  repository      = var.github_repo_name
  secret_name     = "GCP_SA_KEY"
  plaintext_value = base64decode(google_service_account_key.deploy.private_key)
}

# Build-time base URL for the Cloudflare Pages frontend bundle.
resource "github_actions_variable" "vite_backend_url" {
  repository    = var.github_repo_name
  variable_name = "VITE_BACKEND_URL"
  value         = google_cloud_run_v2_service.backend.uri
}

# GCP project id, referenced by google-cloudrun-deploy.yml to build the
# Artifact Registry image path (${{ vars.GCP_PROJECT_ID }}).
resource "github_actions_variable" "gcp_project_id" {
  repository    = var.github_repo_name
  variable_name = "GCP_PROJECT_ID"
  value         = var.gcp_project_id
}
