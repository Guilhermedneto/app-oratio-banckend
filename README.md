# Oratio — API (back-end)

API do **Oratio**, PWA católica de oração diária (pt-BR). FastAPI + SQLAlchemy async + PostgreSQL (Neon).
O front-end fica em outro repositório: **app-oratio-frontend**. Arquitetura e decisões: [docs/plano.md](docs/plano.md);
requisitos: [docs/specs/](docs/specs/).

## O que a API faz

- **Conta**: cadastro, login (e-mail/senha ou Google), refresh rotativo em cookie `httpOnly`, logout.
- **Liturgia**: calendário litúrgico calculado localmente (romano + Brasil) e leituras/orações do dia, vindas de fonte
  pública e guardadas no banco (`/liturgia/hoje`, `/liturgia/{data}`, `/liturgia/semana`).
- **Conteúdo do gestor**: oração, texto, reflexão, rito, Liturgia das Horas, santo, novena e mistérios do terço, com
  autor, origem e categorias (`/conteudos`, `/categorias`, `/gestor/*`).
- **Comunidade**: pedidos de oração, "orei", comentários, moderação e avisos por Web Push (`/comunidade/*`).
- **Dados do usuário**: favoritos, intenções, novenas, terços, preferências, exportar e excluir conta (`/me/*`).

Documentação interativa em `/docs` (OpenAPI em `/openapi.json`).

## Rodar localmente

```bash
docker compose up -d db                 # Postgres na porta 5433 (bancos oratio e oratio_test)
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Linux/macOS: .venv/bin/python
cp .env.example .env                                  # ajuste MANAGER_EMAILS com o seu e-mail
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --port 8010 --reload
```

Crie o banco de testes uma vez: `docker compose exec db psql -U oratio -c "CREATE DATABASE oratio_test;"`.

```bash
.venv/Scripts/python -m pytest          # 90+ testes (usa o banco oratio_test)
.venv/Scripts/ruff check . && .venv/Scripts/mypy app
```

### Perfil gestor

Quem se cadastra ou entra com um e-mail listado em `MANAGER_EMAILS` vira **gestor** (não há tela para promover).
O gestor usa o painel do front para cadastrar conteúdos e moderar a comunidade.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `ENV` | sim | `dev` ou `prod`. Em `prod`, cookies `Secure` e segredo JWT forte são exigidos |
| `DATABASE_URL` | sim | String do Postgres. Aceita a do Neon como vem (`postgresql://…?sslmode=require`) |
| `JWT_SECRET` | sim | Segredo longo e aleatório, mínimo 32 caracteres (em `prod` a API não sobe sem ele) |
| `CORS_ORIGINS` | prod | URL do front (separe várias por vírgula) |
| `MANAGER_EMAILS` | não | E-mails que viram gestores |
| `LITURGY_SOURCES` | não | Fontes de leitura em ordem (padrão `railway`; `sample` só em dev) |
| `GOOGLE_CLIENT_ID` | não | Habilita "Entrar com Google" |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | não | Web Push (lembretes e avisos da comunidade). Gere com `npx web-push generate-vapid-keys` |

## Deploy (Neon + Render + Vercel)

Passo a passo completo, com os cliques e as conferências, em **[docs/DEPLOY.md](docs/DEPLOY.md)**. Resumo:

1. **Neon** (banco): crie o projeto e copie a connection string **com pooler**.
2. **Render** (esta API): crie o serviço a partir de [render.yaml](render.yaml) (ou do [Dockerfile](Dockerfile)) e preencha
   `DATABASE_URL`, `CORS_ORIGINS` e `MANAGER_EMAILS`. As migrations rodam sozinhas no início.
3. **GitHub Actions** ([.github/workflows/jobs.yml](.github/workflows/jobs.yml)): pré-carga diária de leituras, lembretes
   push e ping contra hibernação (os Cron Jobs do Render são pagos).
4. **Vercel** (front): aponte o `rewrite` de `/api/*` para a URL do Render (veja o repositório do front).

## Estrutura

```
app/
  core/          config, banco, segurança, limite de requisições
  routers/       HTTP (auth, liturgia, usuario, conteudos, gestor, comunidade)
  services/      regras de negócio (calendário litúrgico, comunidade, conteúdo…)
  repositories/  acesso a dados (SQL só aqui)
  models/        tabelas SQLAlchemy        schemas/   contrato Pydantic
  integrations/  fontes de leitura, Google, Web Push
  jobs/          prefetch (leituras) e send_push (lembretes)
migrations/      Alembic (toda mudança de esquema passa por aqui)
tests/           pytest (+ fixtures de respostas reais da fonte de leituras)
```

## Direitos autorais

O texto litúrgico (CNBB) tem direitos autorais; o projeto é para **uso pessoal**. Não abra o cache de leituras ao
público nem publique o app sem licença. Os conteúdos do gestor são responsabilidade de quem os cadastra.
