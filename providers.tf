terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  credentials = file("terraform-deployer-key.json")
}

terraform {
  backend "gcs" {
    bucket = "zachle-demo1-tfstate"
    prefix = "vpc"
    credentials = "terraform-deployer-key.json"
  }
}