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

variable "certificate_arn" {
  description = "ACM certificate ARN for the ALB. When set, the ALB serves HTTPS (TLS 1.2+) and port 80 redirects to it. Empty = plain HTTP, development only."
  type        = string
  default     = ""
}

variable "report_ai" {
  description = "Report analysis engine: rules (local, nothing leaves the deployment) or nim (sends report text to the NVIDIA NIM endpoint)."
  type        = string
  default     = "rules"

  validation {
    condition     = contains(["rules", "nim"], var.report_ai)
    error_message = "report_ai must be \"rules\" or \"nim\"."
  }
}

variable "nim_api_key" {
  description = "NVIDIA NIM API key — set via TF_VAR_nim_api_key env var, never hardcoded"
  sensitive   = true
  default     = ""
}
