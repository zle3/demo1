variable "project_id" {
  type = string
  default = "demo1-500618"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "my_app_image_repo" {
  type    = string
  default = "us-central1-docker.pkg.dev/demo1-500618/my-app-repo/my-app"
}

variable "my_app_image_tag" {
  type    = string
  default = "v4"
}