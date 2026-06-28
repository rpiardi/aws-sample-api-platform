data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  for_each           = local.functions
  name               = "${each.value.name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  for_each = local.functions
  statement {
    actions   = each.value.actions
    resources = [aws_dynamodb_table.items.arn]
  }
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda[each.key].arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.functions
  name     = "${each.value.name}-policy"
  role     = aws_iam_role.lambda[each.key].id
  policy   = data.aws_iam_policy_document.lambda[each.key].json
}
