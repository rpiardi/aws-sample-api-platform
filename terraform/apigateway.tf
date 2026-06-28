resource "aws_api_gateway_rest_api" "api" {
  name = "sample-api"
  endpoint_configuration { types = ["REGIONAL"] }
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "auth-platform"
  rest_api_id     = aws_api_gateway_rest_api.api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [data.terraform_remote_state.auth_platform.outputs.user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "v1"
}
resource "aws_api_gateway_resource" "items" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "items"
}
resource "aws_api_gateway_resource" "item" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.items.id
  path_part   = "{itemId}"
}

resource "aws_api_gateway_request_validator" "body" {
  name                        = "validate-body"
  rest_api_id                 = aws_api_gateway_rest_api.api.id
  validate_request_body       = true
  validate_request_parameters = false
}

resource "aws_api_gateway_model" "write" {
  name         = "ItemWrite"
  rest_api_id  = aws_api_gateway_rest_api.api.id
  content_type = "application/json"
  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    type      = "object", additionalProperties = false
    required  = ["description", "status"]
    properties = {
      description = { type = "string", minLength = 1 }
      status      = { type = "boolean" }
    }
  })
}
resource "aws_api_gateway_model" "patch" {
  name         = "ItemPatch"
  rest_api_id  = aws_api_gateway_rest_api.api.id
  content_type = "application/json"
  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    type      = "object", additionalProperties = false, minProperties = 1
    properties = {
      description = { type = "string", minLength = 1 }
      status      = { type = "boolean" }
    }
  })
}

locals {
  api_methods = {
    post     = { verb = "POST", resource = aws_api_gateway_resource.items.id, function = "post", scope = "m2m-prd/write", model = "write" }
    get_list = { verb = "GET", resource = aws_api_gateway_resource.items.id, function = "get", scope = "m2m-prd/read", model = null }
    get_item = { verb = "GET", resource = aws_api_gateway_resource.item.id, function = "get", scope = "m2m-prd/read", model = null }
    put      = { verb = "PUT", resource = aws_api_gateway_resource.item.id, function = "put", scope = "m2m-prd/write", model = "write" }
    patch    = { verb = "PATCH", resource = aws_api_gateway_resource.item.id, function = "patch", scope = "m2m-prd/write", model = "patch" }
    delete   = { verb = "DELETE", resource = aws_api_gateway_resource.item.id, function = "delete", scope = "m2m-prd/write", model = null }
  }
}

resource "aws_api_gateway_method" "method" {
  for_each             = local.api_methods
  rest_api_id          = aws_api_gateway_rest_api.api.id
  resource_id          = each.value.resource
  http_method          = each.value.verb
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  authorization_scopes = [each.value.scope]
  request_validator_id = each.value.model == null ? null : aws_api_gateway_request_validator.body.id
  request_models = each.value.model == "write" ? { "application/json" = aws_api_gateway_model.write.name } : (
    each.value.model == "patch" ? { "application/json" = aws_api_gateway_model.patch.name } : {}
  )
}

resource "aws_api_gateway_integration" "lambda" {
  for_each                = local.api_methods
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = each.value.resource
  http_method             = aws_api_gateway_method.method[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.function[each.value.function].invoke_arn
}

resource "aws_lambda_permission" "api" {
  for_each      = local.api_methods
  statement_id  = "AllowApiGateway${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.function[each.value.function].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/${each.value.verb}${each.key == "get_list" || each.key == "post" ? "/v1/items" : "/v1/items/*"}"
}

resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  triggers = {
    redeployment = sha1(jsonencode({
      methods      = aws_api_gateway_method.method
      integrations = aws_api_gateway_integration.lambda
      models       = [aws_api_gateway_model.write.schema, aws_api_gateway_model.patch.schema]
    }))
  }
  lifecycle { create_before_destroy = true }
}

resource "aws_api_gateway_stage" "prd" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.stage
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId      = "$context.requestId", ip = "$context.identity.sourceIp",
      requestTime    = "$context.requestTime", httpMethod = "$context.httpMethod",
      resourcePath   = "$context.resourcePath", status = "$context.status",
      responseLength = "$context.responseLength"
    })
  }
}
