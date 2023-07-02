output "function_uri" {
  value = google_cloudfunctions2_function.bot.service_config[0].uri
}
