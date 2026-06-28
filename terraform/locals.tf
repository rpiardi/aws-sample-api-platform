locals {
  functions = {
    post   = { name = "sample-integration-post", actions = ["dynamodb:PutItem"] }
    get    = { name = "sample-integration-get", actions = ["dynamodb:GetItem", "dynamodb:Scan"] }
    put    = { name = "sample-integration-put", actions = ["dynamodb:PutItem"] }
    patch  = { name = "sample-integration-patch", actions = ["dynamodb:UpdateItem"] }
    delete = { name = "sample-integration-delete", actions = ["dynamodb:DeleteItem"] }
  }
}
