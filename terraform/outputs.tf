output "api_url" {
  description = "API Gateway stage invoke URL."
  value       = aws_api_gateway_stage.prd.invoke_url
}
output "api_id" {
  description = "API Gateway REST API ID."
  value       = aws_api_gateway_rest_api.api.id
}
output "api_custom_domain_url" {
  description = "Public items collection URL through the existing custom domain."
  value       = "https://${var.custom_domain_name}/${var.custom_domain_base_path}/v1/items"
}
