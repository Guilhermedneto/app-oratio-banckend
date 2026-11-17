# Deploy do Oratio: Neon (banco) + Render (API) + Vercel (front)

Ordem recomendada: **1) Neon → 2) Render → 3) Vercel → 4) voltar ao Render (CORS) → 5) GitHub Actions → 6) conferências**.
Tudo roda nos planos gratuitos. Nada aqui foi executado por mim (não tenho acesso às suas contas): são os passos para você fazer.

## 0. Antes de começar

- Os dois repositórios no GitHub: `app-oratio-banckend` (esta API) e `app-oratio-frontend` (o app), já com o código enviado.
- Um segredo para o login: gere um valor aleatório de 40+ caracteres, por exemplo com
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`. O Render pode gerá-lo sozinho (`generateValue` no `render.yaml`).
- (Opcional) Chaves de push: `npx web-push generate-vapid-keys` (guarde a pública e a privada).

## 1. Neon — banco de dados

1. Crie a conta em <https://neon.tech> e **New project**: nome `oratio`, Postgres 16, região **AWS South America (São Paulo)**.
2. No painel do projeto, clique em **Connect**. Deixe **Connection pooling ligado** e copie a string. Ela é parecida com:
   `postgresql://oratio_owner:SENHA@ep-xxxx-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require`
   - **Use a string com `-pooler` no endereço** (o app já desativa o cache de prepared statements, exigido pelo pooler).
   - Pode colar do jeito que vem: o app converte `postgresql://` e `sslmode=require` sozinho.
3. (Recomendado) Crie uma segunda *branch* `dev` para testes e deixe a `main` como produção.
4. Guarde a string: ela vai em `DATABASE_URL` no Render e no GitHub Actions. **Nunca a coloque no repositório.**

O esquema do banco é criado pelas migrations (Alembic), que rodam sozinhas toda vez que a API sobe.

## 2. Render — API

1. Em <https://render.com>, **New → Blueprint** e conecte o repositório `app-oratio-banckend`.
   O Render lê o [render.yaml](../render.yaml) e propõe o serviço `oratio-api` (plano **Free**).
   - Alternativa sem blueprint: **New → Web Service**, runtime *Python 3.12*, Build `pip install .`,
     Start `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Health check `/health`.
     Ou escolha *Docker* e use o [Dockerfile](../Dockerfile).
2. Preencha as variáveis (as marcadas como "sync: false"):

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | a string do Neon (passo 1) |
   | `CORS_ORIGINS` | por enquanto `http://localhost:5173`; troque no passo 4 pela URL da Vercel |
   | `MANAGER_EMAILS` | o seu e-mail (vira gestor ao cadastrar/entrar) |
   | `JWT_SECRET` | gerado pelo Render (ou o seu, 32+ caracteres) |
   | `ENV` | `prod` (já no blueprint) |
   | `LITURGY_SOURCES` | `railway` (já no blueprint) |
   | `VAPID_*`, `GOOGLE_CLIENT_ID` | opcionais |

3. **Apply / Deploy**. O primeiro build leva alguns minutos.
4. Quando ficar *Live*, abra `https://SEU-SERVICO.onrender.com/health`. Deve responder `{"status":"ok","db":"ok"}`.
   Se `db` vier `unavailable`, a `DATABASE_URL` está errada (veja a seção de problemas).
5. Anote a URL do serviço. No plano gratuito a API **hiberna** após ~15 min sem uso; a primeira chamada demora ~1 min.
   O ping do passo 5 reduz isso, e o app já abre do cache sem esperar a API.

## 3. Vercel — front-end

Os detalhes estão no README do repositório `app-oratio-frontend`. Em resumo:

1. Em <https://vercel.com>, **Add New → Project** e importe `app-oratio-frontend` (framework detectado: **Vite**).
2. **Antes do deploy**, edite `vercel.json` do front: troque `https://SEU-SERVICO.onrender.com` pela URL do Render (passo 2.5)
   e envie o commit. É esse *rewrite* que faz o navegador falar com a API na **mesma origem** (cookies funcionam no Safari/iPhone).
3. Variáveis de ambiente (opcionais): `VITE_API_BASE=/api`, `VITE_VAPID_PUBLIC_KEY`, `VITE_GOOGLE_CLIENT_ID`.
4. **Deploy**. Anote a URL (ex.: `https://oratio.vercel.app`).

## 4. Voltar ao Render — CORS

No serviço `oratio-api`, edite `CORS_ORIGINS` para a URL da Vercel (sem barra no final) e salve (o Render reinicia).
Se usar domínio próprio, coloque os dois separados por vírgula.

## 5. GitHub Actions — jobs agendados e ping

No repositório do back, em **Settings → Secrets and variables → Actions**:

- **Secrets**: `DATABASE_URL` (a do Neon), `JWT_SECRET` (a mesma do Render), `LITURGY_SOURCES` (`railway`, opcional),
  `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (se usar push).
- **Variables**: `API_URL` = a URL do Render (liga o ping a cada 10 min contra a hibernação).

O workflow [jobs.yml](../.github/workflows/jobs.yml) pré-carrega 14 dias de liturgia todo dia às 05:00 (Brasília) e envia
os lembretes a cada 15 min. Teste uma vez em **Actions → Jobs agendados → Run workflow**.

## 6. Conferências depois do deploy

- [ ] `https://API/health` → `ok` e `db: ok`.
- [ ] `https://API/liturgia/hoje` devolve a liturgia (tempo, cor e leituras).
- [ ] Abra o front, **crie a conta com o e-mail de `MANAGER_EMAILS`** e confira que **Mais → Painel do gestor** aparece.
- [ ] No painel, cadastre as orações do terço com os identificadores exatos (`sinal-da-cruz`, `credo`, `pai-nosso`, `ave-maria`,
      `gloria`, `o-meu-jesus`, `salve-rainha`, `oracao-final-do-terco`) e um conjunto de mistérios.
- [ ] iPhone: abra no **Safari → Compartilhar → Adicionar à Tela de Início**; o push só funciona com o app instalado (iOS 16.4+).
- [ ] Desligue o modo avião depois de abrir uma vez: o app deve abrir offline para quem já entrou.

## Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `/health` mostra `db: unavailable` | `DATABASE_URL` errada ou sem pooler. Copie de novo do Neon; não remova `sslmode=require` |
| API não sobe em `prod` | `JWT_SECRET` ausente ou com menos de 32 caracteres |
| Primeira chamada demora muito / 502 | API hibernada (plano gratuito) ou banco do Neon acordando; tente de novo em ~1 min |
| Login "funciona" mas some ao recarregar | O front não está usando o *rewrite* `/api` (cookies entre domínios). Confira o `vercel.json` |
| Erro de CORS no navegador | `CORS_ORIGINS` não tem exatamente a URL do front |
| Sem leituras do dia | A fonte pública pode estar fora do ar; o app mostra tempo, cor e celebração e avisa. Veja os logs |
| Lembretes não chegam | Falta `VAPID_*`, o app não está instalado no iPhone, ou o workflow `jobs.yml` está desativado |

## Direitos autorais

O texto litúrgico da CNBB tem direitos autorais. Use **apenas de forma pessoal** e não abra o app ao público sem licença.
