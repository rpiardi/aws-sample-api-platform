# sample-api-platform

API REST `v1/items` implementada com API Gateway, Lambdas Python e DynamoDB.
O acesso exige um access token do `auth-platform`; o API Gateway valida o
token e os escopos `m2m-prd/read` ou `m2m-prd/write`.

## Validação local

```bash
python3 -m unittest discover -s tests -v
tofu fmt -check -recursive
cd terraform
tofu init -backend=false -input=false -lockfile=readonly
tofu validate
```

## Planejamento e implantação

O backend e o estado remoto de autenticação exigem acesso AWS ao account
`209479281611`. Para planejamento autorizado:

```bash
cd terraform
tofu init
tofu plan
```

O workflow manual `OpenTofu Deploy` executa plan e apply no mesmo job, somente
na branch protegida `main` e no environment `prd`. Configure
`vars.AWS_ROLE_ARN` como:

```text
arn:aws:iam::209479281611:role/SampleApiPlatformGitHubDeployer
```

## API

- `POST /prd/v1/items`
- `GET /prd/v1/items?limit=50&cursor=<opaque>`
- `GET /prd/v1/items/{itemId}`
- `PUT /prd/v1/items/{itemId}`
- `PATCH /prd/v1/items/{itemId}`
- `DELETE /prd/v1/items/{itemId}`

Exemplo de escrita (não registre o token):

```bash
curl -X POST "$API_URL/v1/items" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"description":"example","status":true}'
```

Erros de aplicação usam `{"error":"ValidationError","message":"..."}`.
Nenhum comando de implantação é necessário para executar os testes locais.
