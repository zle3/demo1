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
      image = local.my_app_docker_repo
      ports {
        container_port = 8080
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
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
          image: ${local.my_app_docker_repo}
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

resource "google_compute_region_network_endpoint_group" "cloudrun_neg" {
  name                  = "cloudrun-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  cloud_run {
    service = google_cloud_run_v2_service.my_app.name
  }
}

resource "google_compute_backend_service" "my_app_backend" {
  name                  = "my-app-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.cloudrun_neg.id
  }
}

resource "google_compute_url_map" "my_app_url_map" {
  name            = "my-app-url-map"
  default_service = google_compute_backend_service.my_app_backend.id
}

resource "google_compute_managed_ssl_certificate" "my_app_cert" {
  name = "my-app-cert"
  managed {
    domains = ["demo1.zachle.info"]
  }
}

resource "google_compute_target_https_proxy" "my_app_https_proxy" {
  name             = "my-app-https-proxy"
  url_map          = google_compute_url_map.my_app_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.my_app_cert.id]
}

resource "google_compute_global_address" "my_app_lb_ip" {
  name = "my-app-lb-ip"
}

resource "google_compute_global_forwarding_rule" "my_app_forwarding_rule" {
  name                  = "my-app-forwarding-rule"
  target                = google_compute_target_https_proxy.my_app_https_proxy.id
  port_range            = "443"
  ip_address            = google_compute_global_address.my_app_lb_ip.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_cloudbuildv2_connection" "github" {
  location = "us-central1"
  name     = "github-connection"

  lifecycle {
    ignore_changes = [github_config]
  }
}

resource "google_cloudbuildv2_repository" "demo1" {
  location          = var.region
  name              = "demo1-repo"
  parent_connection = google_cloudbuildv2_connection.github.name
  remote_uri        = "https://github.com/zle3/demo1.git"
}

resource "google_cloudbuild_trigger" "demo1_main" {
  name            = "demo1-main-trigger"
  location        = var.region
  service_account = "projects/demo1-500618/serviceAccounts/cloudbuild-runner@demo1-500618.iam.gserviceaccount.com"

  repository_event_config {
    repository = "projects/demo1-500618/locations/us-central1/connections/github-connection/repositories/demo1-repo"
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  approval_config {
    approval_required = true
  }
}

resource "google_monitoring_uptime_check_config" "site" {
  display_name = "demo1-site-uptime"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = "demo1-500618"
      host       = "demo1.zachle.info"
    }
  }
}

resource "google_project_service" "servicenetworking" {
  project = "demo1-500618"
  service = "servicenetworking.googleapis.com"
}

resource "google_compute_global_address" "private_ip_range" {
  name          = "cloudsql-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
  depends_on              = [google_project_service.servicenetworking]
}

resource "google_sql_database_instance" "main" {
  name             = "demo1-postgres"
  database_version = "POSTGRES_15"
  region           = "us-central1"
  project          = "demo1-500618"

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "app_db" {
  name     = "demo1"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app_user" {
  name     = "app_user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}

resource "google_vpc_access_connector" "connector" {
  name          = "demo1-vpc-connector"
  region        = "us-central1"
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_project_iam_member" "cloudrun_sql_client" {
  project = "demo1-500618"
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:543077399900-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "vm_sql_client" {
  project = "demo1-500618"
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.vm_runtime.email}"
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "demo1-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

resource "google_secret_manager_secret_iam_member" "cloudrun_secret_access" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:543077399900-compute@developer.gserviceaccount.com"
}