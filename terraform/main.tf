terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }

  backend "gcs" {
    bucket = "org-bot-tf-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

resource "random_id" "default" {
  byte_length = 8
}

resource "google_storage_bucket" "default" {
  name                        = "${random_id.default.hex}-gcf-source" # Every bucket name must be globally unique
  location                    = var.region
  uniform_bucket_level_access = true
}

data "archive_file" "default" {
  type        = "zip"
  output_path = "/tmp/function-source.zip"
  source_dir  = abspath("${path.module}/../src/") # Relative to project root
}

locals {
  source_code_hash = filemd5(data.archive_file.default.output_path)
  config = merge(
    yamldecode(file(abspath("${path.module}/../config/${var.namespace}/config.yaml"))), # Relative to project root
    { "NAMESPACE" = var.namespace }
  )
}

resource "google_storage_bucket_object" "object" {
  name   = "function-source-${local.source_code_hash}.zip"
  bucket = google_storage_bucket.default.name
  source = data.archive_file.default.output_path # Add path to the zipped function source code


}

resource "google_cloudfunctions2_function" "bot" {
  name        = var.name
  description = var.description

  location = var.region

  build_config {
    runtime     = "python311"
    entry_point = "http_entrypoint" # Set the entry point
    source {
      storage_source {
        bucket = google_storage_bucket.default.name
        object = google_storage_bucket_object.object.name
      }
    }

  }

  service_config {
    max_instance_count    = 1
    max_instance_request_concurrency = 80
    available_cpu         = "1"
    available_memory      = "256M"
    timeout_seconds       = 60
    ingress_settings      = "ALLOW_ALL"
    environment_variables = local.config
  }
}


resource "google_cloudfunctions2_function_iam_member" "v2invoker" {
  depends_on = [google_cloudfunctions2_function.bot]

  project        = google_cloudfunctions2_function.bot.project
  cloud_function = google_cloudfunctions2_function.bot.name
  location       = google_cloudfunctions2_function.bot.location

  role   = "roles/cloudfunctions.invoker"
  member = "allUsers"
}

resource "google_cloudfunctions2_function_iam_binding" "binding" {
  depends_on = [google_cloudfunctions2_function.bot]

  project        = google_cloudfunctions2_function.bot.project
  location       = google_cloudfunctions2_function.bot.location
  cloud_function = google_cloudfunctions2_function.bot.name
  role           = "roles/cloudfunctions.invoker"
  members        = ["allUsers"]
}


