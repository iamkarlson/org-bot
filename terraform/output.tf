output "function_uri" {
  value = google_cloudfunctions2_function.bot.service_config[0].uri
}

output "bot_name" {
  value = var.name
}

output "bot_region" {
  value = var.region
}

output "bot_project" {
  value = var.project
}