# Oratio API — regras de trabalho

- Leia docs/plano.md e docs/specs/ antes de qualquer tarefa.
- Respeite a separação: routers (HTTP) -> services (regras) -> repositories (SQL) -> models. Nada de SQL em router.
- Migrations só via Alembic. Nunca alterar o banco na mão.
- O front gera os tipos TypeScript a partir do OpenAPI desta API: mudou um schema, avise/regenere no repositório do front.
- Integrações externas (fontes de leitura, Google, Web Push) só em `app/integrations/`.
- Segredos só em variáveis de ambiente; nunca no repositório.
- Cada mudança com teste. Rodar `ruff check .`, `mypy app` e `pytest` antes de concluir.
- Idioma das mensagens ao usuário: português do Brasil.

## Comandos

- Banco local: `docker compose up -d db` (porta 5433; bancos `oratio` e `oratio_test`).
- `.venv/Scripts/python -m pytest`, `ruff check .`, `mypy app`, `alembic upgrade head`,
  `uvicorn app.main:app --port 8010`.
- OpenAPI para o front: `python -m app.export_openapi openapi.json`.
