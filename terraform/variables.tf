variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "stage" {
  type    = string
  default = "prd"
}
variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}
variable "lambda_memory_size" {
  type    = number
  default = 128
}
variable "lambda_timeout" {
  type    = number
  default = 10
}
variable "log_retention_days" {
  type    = number
  default = 14
}
variable "custom_domain_name" {
  description = "Existing API Gateway custom domain managed outside this repository."
  type        = string
  default     = "minha-api.freeddns.org"
}
variable "custom_domain_base_path" {
  description = "Base path used to expose this API on the existing custom domain."
  type        = string
  default     = "sample-api"
}
