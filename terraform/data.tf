data "terraform_remote_state" "auth_platform" {
  backend = "s3"
  config = {
    bucket = "rogerio-iac-prod-us-east-1"
    key    = "rogerio.piardi/terraform/auth-platform/prd.tfstate"
    region = "us-east-1"
  }
}
