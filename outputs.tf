output "load_balancer_ip" {
  value = google_compute_global_address.my_app_lb_ip.address
}