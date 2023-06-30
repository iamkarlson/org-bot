terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

provider "google" {
  project = "org-bot-389717"
  region  = "europe-west1"
}

resource "random_id" "default" {
  byte_length = 8
}

resource "google_storage_bucket" "default" {
  name                        = "${random_id.default.hex}-gcf-source" # Every bucket name must be globally unique
  location                    = "EUROPE-WEST1"
  uniform_bucket_level_access = true
}

data "archive_file" "default" {
  type        = "zip"
  output_path = "/tmp/function-source.zip"
  source_dir  = "src/"
}

resource "google_storage_bucket_object" "object" {
  name   = "function-source.zip"
  bucket = google_storage_bucket.default.name
  source = data.archive_file.default.output_path # Add path to the zipped function source code
}

resource "google_cloudfunctions2_function" "default" {
  name        = "brain-bot"
  description = "iamkarlson brain bot"
  location = "europe-west1"
  build_config {
    runtime     = "python311"
    entry_point = "handle" # Set the entry point
    source {
      storage_source {
        bucket = google_storage_bucket.default.name
        object = google_storage_bucket_object.object.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 60
    ingress_settings   = "ALLOW_ALL"
    environment_variables = {
      BOT_TOKEN = file("${path.module}/bot_token.txt")
    }
  }
}
resource "google_cloudfunctions_function_iam_binding" "binding" {
  cloud_function = google_cloudfunctions2_function.default.name
  role = "roles/cloudfunctions.invoker"
  members = [
    "allUsers",
  ]
}

output "function_uri" {
  value = google_cloudfunctions2_function.default.service_config[0].uri
}
