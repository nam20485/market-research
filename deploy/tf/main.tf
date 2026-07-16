terraform {
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "~> 4.0" }
    github     = { source = "integrations/github", version = "~> 5.0" }
    google     = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "github" {
  token = var.github_token
  owner = var.github_username
}

# NB: this resource's `name` must stay identical to the `projectName` input
# used by .github/workflows/cloudflare_deploy.yml's cloudflare/pages-action
# step. Do not let them drift apart.
resource "cloudflare_pages_project" "market_research" {
  account_id        = var.cloudflare_account_id
  name              = "market-research"
  production_branch = "main"

  build_config {
    build_command   = "pnpm install && pnpm build"
    destination_dir = "dist"
    root_dir        = "frontend"
  }

  source {
    type = "github"

    config {
      owner             = var.github_username
      repo_name         = var.github_repo_name
      production_branch = "main"
    }
  }
}

resource "github_actions_secret" "cf_api_token" {
  repository      = var.github_repo_name
  secret_name     = "CLOUDFLARE_API_TOKEN"
  plaintext_value = var.cloudflare_api_token
}

resource "github_actions_secret" "cf_account_id" {
  repository      = var.github_repo_name
  secret_name     = "CLOUDFLARE_ACCOUNT_ID"
  plaintext_value = var.cloudflare_account_id
}

# Deliberately no null_resource/local-exec workflow trigger here (unlike the
# intel-agency-com-v2 reference) — deploys stay fully manual per the plan's
# "DO NOT ACTUALLY DEPLOY YET" instruction. A human runs
# `gh workflow run cloudflare_deploy.yml` (or the Actions UI) explicitly when
# ready.
