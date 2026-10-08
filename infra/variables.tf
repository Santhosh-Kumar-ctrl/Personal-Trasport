variable "region" {
  default = "ap-south-1"
}

variable "project" {
  default = "bus-tracking"
}

variable "db_name" {
  default = "transit"
}

variable "db_username" {
  default = "transit"
}

variable "container_cpu" {
  default = 256
}

variable "container_memory" {
  default = 512
}

variable "domain" {
  description = "Optional: custom domain for the ALB HTTPS listener (leave empty to use ALB DNS)"
  default     = ""
}

variable "nim_api_key" {
  description = "NVIDIA NIM API key — set via TF_VAR_nim_api_key env var, never hardcoded"
  sensitive   = true
}
