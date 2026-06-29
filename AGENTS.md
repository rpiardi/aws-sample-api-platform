# AGENTS.md

## Project

This repository contains the infrastructure and Lambda code for the
`sample-api-platform` logical project.

The repository name is:

```text
aws-sample-api-platform
```

The platform exposes the `items` business API through API Gateway REST,
Lambda proxy integrations, and DynamoDB.

The `auth-platform` is an external platform. This repository must not create,
change, duplicate, or manage Cognito resources. It consumes only the
`user_pool_arn` output from the auth platform through `terraform_remote_state`.

## Architecture

Request flow:

```text
Consumer
   ↓ Authorization: Bearer <access token>
API Gateway REST + Cognito User Pool Authorizer + request validation
   ↓ Lambda proxy integration selected by HTTP verb
Lambda handler + common Lambda Layer
   ↓
DynamoDB
```

Use one Lambda per write verb and one shared Lambda for both GET routes:

```text
POST   /items          → sample-integration-post
GET    /items          → sample-integration-get
GET    /items/{itemId} → sample-integration-get
PUT    /items/{itemId} → sample-integration-put
PATCH  /items/{itemId} → sample-integration-patch
DELETE /items/{itemId} → sample-integration-delete
```

Shared code belongs in the Lambda Layer:

```text
sample-integration-common
```

Handlers must remain thin. Put DynamoDB access, semantic validation, UUID
generation, and response/error helpers in the common layer.

Do not add:

- a backend HTTP service behind the Lambdas;
- Lambda-to-Lambda invocation;
- a Lambda authorizer;
- Cognito management or Cognito API calls;
- Secrets Manager integration for authentication;
- a NAT Gateway for DynamoDB access.

## Fixed AWS Context

Use:

```text
AWS account = 209479281611
AWS region  = us-east-1
stage       = prd
```

## Canonical Naming

These names are final and replace older names found in source specifications:

| Item | Canonical value |
| --- | --- |
| Repository | `aws-sample-api-platform` |
| Logical project | `sample-api-platform` |
| API Gateway REST API | `sample-api` |
| DynamoDB table | `sample-items` |
| POST Lambda | `sample-integration-post` |
| GET Lambda | `sample-integration-get` |
| PUT Lambda | `sample-integration-put` |
| PATCH Lambda | `sample-integration-patch` |
| DELETE Lambda | `sample-integration-delete` |
| Lambda Layer | `sample-integration-common` |
| GitHub OIDC role | `SampleApiPlatformGitHubDeployer` |
| State concurrency group | `sample-api-platform-prd-state` |

Do not reintroduce names such as `business-platform`, `items-post`, or an
`aws-` prefix in logical project or AWS resource names.

Apply only this project tag to taggable resources unless an AWS requirement
demands an additional tag:

```text
Project = sample-api-platform
```

## API Contract

The API version is `v1` and the resource is `items`.

The item model is:

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `id` | string | yes in stored/returned items | UUID v4 generated on POST |
| `description` | string | yes on POST and PUT | non-empty after trimming |
| `status` | boolean | yes on POST and PUT | `true` active, `false` inactive |

Behavior:

- POST creates an item and returns `201`.
- GET collection uses a paginated DynamoDB `Scan` and returns `200` with
  `{"items": [...], "cursor": "<opaque>"}`. The cursor is `null` on the last
  page.
- GET by ID returns `200` or `404`.
- PUT performs a full upsert and returns `200`.
- PATCH updates at least one supported field, requires the item to exist, and
  returns `200`, `400`, or `404`.
- DELETE is idempotent and returns `204`, including when the item is absent.

Use API Gateway request models and a request validator for POST, PUT, and
PATCH. Reject unknown fields. Keep residual semantic validation in the common
layer, especially trimmed empty descriptions.

Application errors use:

```json
{"error": "ValidationError", "message": "..."}
```

Supported application error codes are `ValidationError`, `NotFound`,
`Forbidden`, and `InternalError`. Do not leak stack traces or internal AWS
errors to callers. `Forbidden` (HTTP 403) is returned only by the partner
identity defense-in-depth check described under Authorization.

## Authorization

Use an API Gateway `COGNITO_USER_POOLS` authorizer. Read its sole provider ARN
from:

```hcl
data.terraform_remote_state.auth_platform.outputs.user_pool_arn
```

The external state is:

```text
bucket = rogerio-iac-prod-us-east-1
key    = rogerio.piardi/terraform/auth-platform/prd.tfstate
region = us-east-1
```

Do not consume any other auth-platform output unless the requirements are
explicitly changed.

Required scopes:

```text
GET                         = m2m-prd/read
POST, PUT, PATCH, DELETE    = m2m-prd/write
```

Token validation and scope enforcement happen at API Gateway before Lambda
invocation.

### Partner identity (Approach A)

The auth-platform resolves the calling client to a partner identity
(`partner_id`, `tenant`) at token issuance and signs it into the access token.
The native authorizer exposes those claims under
`requestContext.authorizer.claims`.

This repository only consumes the claims; it never resolves identity and never
reads the `auth-partners` table:

- the common layer reads `partner_id`/`tenant` from the claims and validates
  their presence (defense in depth), failing closed with `403 Forbidden` when
  absent — this is reachable only on misconfiguration, since the authorizer and
  trigger normally guarantee the claims;
- identity is never accepted from headers, query string, or body
  (`X-Partner-Id`/`X-Tenant-Id` are ignored);
- identity is never stored on the item nor returned in any response;
- handlers resolve identity before any DynamoDB access.

Do not add a lookup of partner data in this repository.

## DynamoDB

Create one table:

```text
name         = sample-items
partition key = id (String)
billing mode = PAY_PER_REQUEST
PITR         = enabled
```

Do not add a sort key or secondary indexes without a new requirement.

Grant each Lambda only its required actions on the `sample-items` table:

| Lambda | DynamoDB actions |
| --- | --- |
| `sample-integration-post` | `dynamodb:PutItem` |
| `sample-integration-get` | `dynamodb:GetItem`, `dynamodb:Scan` |
| `sample-integration-put` | `dynamodb:PutItem` |
| `sample-integration-patch` | `dynamodb:UpdateItem` |
| `sample-integration-delete` | `dynamodb:DeleteItem` |

## Repository Structure

Keep Terraform configuration in `terraform/` and application code in `src/`.
Do not create Terraform submodules unless explicitly requested.

Expected structure:

```text
aws-sample-api-platform/
├── AGENTS.md
├── README.md
├── .github/
│   └── workflows/
│       ├── opentofu-ci.yml
│       ├── opentofu-deploy.yml
│       └── test-aws-oidc.yml
├── docs/
├── src/
│   ├── common/python/sample_common/
│   ├── post/lambda_function.py
│   ├── get/lambda_function.py
│   ├── put/lambda_function.py
│   ├── patch/lambda_function.py
│   └── delete/lambda_function.py
├── tests/
└── terraform/
    ├── backend.tf
    ├── versions.tf
    ├── providers.tf
    ├── variables.tf
    ├── locals.tf
    ├── data.tf
    ├── dynamodb.tf
    ├── lambda.tf
    ├── iam.tf
    ├── apigateway.tf
    ├── logs.tf
    └── outputs.tf
```

## OpenTofu

Use OpenTofu `1.11.5`.

Use the existing S3 backend:

```text
bucket = rogerio-iac-prod-us-east-1
key    = rogerio.piardi/terraform/sample-api-platform/prd.tfstate
region = us-east-1
```

Enable:

```hcl
use_lockfile = true
```

Do not create a DynamoDB lock table.

Organize Terraform files by responsibility. Prefer variables with defaults for
operational values such as region, stage, Lambda memory/timeout, and log
retention. Keep the fixed architecture and canonical resource names explicit;
do not over-parameterize them.

Package Lambda source deterministically with `archive_file`. Ensure source
hashes drive Lambda and Layer updates. Set explicit CloudWatch log retention.

Before considering an infrastructure change complete, run:

```text
tofu fmt -check -recursive
tofu init -backend=false
tofu validate
```

Do not run `tofu plan` or `tofu apply`, access AWS, or create remote resources
unless the user explicitly requests it.

## Lambda Implementation

Use the Python runtime selected in Terraform consistently in local tests.
Use the standard library and the AWS-provided `boto3`; avoid vendoring
unnecessary dependencies.

Initialize AWS clients/resources at module scope for execution environment
reuse. Read the table name from an environment variable. Do not hardcode table
ARNs or account-specific values in Python.

For collection reads:

- accept a bounded `limit`;
- encode/decode an opaque pagination cursor safely;
- return `LastEvaluatedKey` as a continuation cursor;
- reject malformed pagination input with `400`.

Use conditional updates for PATCH so a missing item returns `404`. Catch
specific expected AWS exceptions and map them to the API contract; map
unexpected failures to `500`.

Tests must mock AWS boundaries and must not require AWS credentials or network
access.

## GitHub Actions

GitHub Actions is the intended CI/CD system.

Workflows must:

- use OpenTofu `1.11.5`;
- run formatting, backend-free initialization, and validation on pull requests;
- keep plan/apply manually triggered with `workflow_dispatch`;
- deploy only from the protected `main` branch and GitHub environment `prd`;
- authenticate through GitHub OIDC using `vars.AWS_ROLE_ARN`;
- expect role
  `arn:aws:iam::209479281611:role/SampleApiPlatformGitHubDeployer`;
- serialize state operations with `sample-api-platform-prd-state`;
- create and apply the saved plan in the same job;
- never publish the saved plan as a public artifact;
- never use long-lived AWS access keys.

Do not publish to GitHub or trigger deployment workflows unless explicitly
requested.

## Safety and Scope

Implementation and local validation do not authorize deployment.

Never, without explicit user authorization:

- run `tofu apply` or any equivalent deployment command;
- create, update, or delete AWS resources;
- invoke AWS CLI commands against the account;
- push commits, open pull requests, or trigger GitHub workflows;
- modify the external `auth-platform` repository or its state.

Preserve the separation of responsibilities: this repository owns the business
API; `auth-platform` owns authentication resources.
