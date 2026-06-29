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

resource "google_artifact_registry_repository" "my_app_repo" {
  location      = var.region
  repository_id = "my-app-repo"
  format        = "DOCKER"
  description   = "Docker images for the GCP project"
}

resource "google_cloud_run_v2_service" "my_app" {
  name     = "my-app-service"
  location = var.region

  template {
    containers {
      image = "us-central1-docker.pkg.dev/demo1-500618/my-app-repo/my-app:v1"
      ports {
        container_port = 8080
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.my_app.location
  name     = google_cloud_run_v2_service.my_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_instance" "my_app_vm" {
  name         = "my-app-vm"
  machine_type = "e2-small"
  zone         = "us-central1-a"
  tags         = ["ssh-allowed"]

  boot_disk {
    initialize_params {
      image = "projects/cos-cloud/global/images/family/cos-stable"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.private.id
    # no access_config block, intentionally, this VM gets no external IP
  }

  metadata = {
    gce-container-declaration = <<-EOT
      spec:
        containers:
        - name: my-app-vm
          image: us-central1-docker.pkg.dev/demo1-500618/my-app-repo/my-app:v1
          ports:
          - containerPort: 8080
        restartPolicy: Always
    EOT
  }

  service_account {
    email  = google_service_account.vm_runtime.email
    scopes = ["cloud-platform"]
  }
}

resource "google_service_account" "vm_runtime" {
  account_id   = "my-app-vm-runtime"
  display_name = "My App VM Runtime"
}