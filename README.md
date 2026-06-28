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

O stage `prd` é associado ao custom domain existente
`minha-api.freeddns.org` pelo base path `sample-api`:

- `POST /sample-api/v1/items`
- `GET /sample-api/v1/items?limit=50&cursor=<opaque>`
- `GET /sample-api/v1/items/{itemId}`
- `PUT /sample-api/v1/items/{itemId}`
- `PATCH /sample-api/v1/items/{itemId}`
- `DELETE /sample-api/v1/items/{itemId}`

### Listagem paginada

`GET /sample-api/v1/items` retorna um envelope com os itens da página e um
cursor opaco para continuação:

```json
{
  "items": [
    {
      "id": "9f1c2e4a-7b3d-4f8e-a1c2-0b9d8e7f6a5c",
      "description": "Item de exemplo",
      "status": true
    }
  ],
  "cursor": "eyJpZCI6IjlmMWMyZTRhLTdiM2QtNGY4ZS1hMWMyLTBiOWQ4ZTdmNmE1YyJ9"
}
```

Use o valor retornado em `cursor` na próxima requisição. O parâmetro `limit`
é opcional, usa `50` por padrão e aceita valores entre `1` e `100`.
Na última página, `cursor` é `null`:

```json
{
  "items": [],
  "cursor": null
}
```

Exemplo de escrita (não registre o token):

```bash
curl -X POST "https://minha-api.freeddns.org/sample-api/v1/items" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"description":"example","status":true}'
```

Erros de aplicação usam `{"error":"ValidationError","message":"..."}`.
Nenhum comando de implantação é necessário para executar os testes locais.
