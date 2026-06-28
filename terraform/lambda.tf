data "archive_file" "common" {
  type        = "zip"
  source_dir  = "${path.module}/../src/common"
  output_path = "${path.module}/common.zip"
}

data "archive_file" "function" {
  for_each    = local.functions
  type        = "zip"
  source_dir  = "${path.module}/../src/${each.key}"
  output_path = "${path.module}/${each.key}.zip"
}

resource "aws_lambda_layer_version" "common" {
  layer_name          = "sample-integration-common"
  filename            = data.archive_file.common.output_path
  source_code_hash    = data.archive_file.common.output_base64sha256
  compatible_runtimes = [var.lambda_runtime]
}

resource "aws_lambda_function" "function" {
  for_each         = local.functions
  function_name    = each.value.name
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = var.lambda_runtime
  handler          = "lambda_function.lambda_handler"
  filename         = data.archive_file.function[each.key].output_path
  source_code_hash = data.archive_file.function[each.key].output_base64sha256
  layers           = [aws_lambda_layer_version.common.arn]
  memory_size      = var.lambda_memory_size
  timeout          = var.lambda_timeout
  environment {
    variables = { TABLE_NAME = aws_dynamodb_table.items.name }
  }
  depends_on = [aws_iam_role_policy.lambda]
}
