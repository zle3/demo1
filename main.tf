resource "google_compute_network" "main" {
  name                    = "homelab-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "public" {
  name          = "public-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling         = 0.5
    metadata              = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "private" {
  name                     = "private-subnet"
  ip_cidr_range            = "10.0.2.0/24"
  region                   = var.region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling         = 0.5
    metadata              = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_router" "main" {
  name    = "homelab-router"
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "homelab-nat"
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.private.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "allow-iap-ssh"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # Google's fixed IAP forwarding range. Not your home IP, and it
  # never changes regardless of your ISP or NAT setup.
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["ssh-allowed"]
}

resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  source_ranges = ["10.0.0.0/16"]
}