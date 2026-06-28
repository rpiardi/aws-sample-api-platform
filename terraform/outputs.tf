output "api_url" {
  value = aws_api_gateway_stage.prd.invoke_url
}
output "api_id" {
  value = aws_api_gateway_rest_api.api.id
}
