output "load_balancer_ip" {
  value = google_compute_global_address.my_app_lb_ip.address
}

output "uptime_check_id" {
  value = google_monitoring_uptime_check_config.site.uptime_check_id
}