# Oratio — Plano de desenvolvimento

> **Nota (repositórios):** o projeto foi dividido em dois repositórios: **app-oratio-banckend** (API, banco e jobs; este) e
> **app-oratio-frontend** (PWA React). As pastas `api/`, `web/` e `content/` citadas abaixo correspondem a esses repositórios.
> O conteúdo (orações, textos, santos, novenas, mistérios) passou a ser cadastrado pelo perfil **gestor**, não mais por arquivos.


App PWA de oração diária (católico, pt-BR): liturgia do dia, tempo e cor litúrgica, terço, novenas, orações, ritos e reflexões.
Uso pessoal, com login desde o início. Prioridade: **leve, rápido e funcionando offline**.

| Camada | Tecnologia | Hospedagem |
|---|---|---|
| Front | React + TypeScript + Vite (PWA) | Vercel |
| Back | Python + FastAPI | Render |
| Banco | PostgreSQL | Neon |

> Este arquivo é a fonte de verdade do projeto. Ao usar o Claude Code, mantenha-o na raiz e peça para ele seguir as seções "Responsabilidades" e "Regras" abaixo.

---

## 1. Princípios

1. **Offline primeiro.** Tudo que não muda por dia (orações, terço, novenas, ritos) vive no dispositivo. A API só entrega o que é dinâmico.
2. **Responsabilidades separadas.** Cada camada tem um dono claro (seção 2). Nada de lógica de negócio no banco nem regra de dados no front.
3. **Contrato único.** A API FastAPI gera o OpenAPI; o front gera os tipos TypeScript a partir dele. Nunca duplicar tipos à mão.
4. **Leve.** Orçamento de desempenho (seção 3) é requisito, não desejo.
5. **O front nunca chama fontes externas.** Só a nossa API fala com fontes de leitura.
6. **Cache agressivo, coleta mínima.** Uma coleta por dia por fonte externa, guardada no banco.

---

## 2. Responsabilidades por camada

### 2.1 Front (React / Vercel)
**É dono de:** interface, navegação, estado de tela, modo offline, instalação PWA, cache do Service Worker, estado local do terço e das novenas, tema, acessibilidade, notificações (assinatura do navegador).

**Não faz:** calcular calendário litúrgico, falar com fontes de leitura, validar regra de negócio, acessar banco.

- Conteúdo estático (orações, mistérios, novenas, ritos) fica em `content/` como Markdown/JSON, **empacotado no build** e carregado sob demanda por rota.
- Lê a API só para: liturgia do dia, dados do usuário (progresso, favoritos, intenções, preferências) e push.
- Estratégia de dados: **stale-while-revalidate**. Abre instantâneo com o último dado salvo e atualiza em segundo plano.

### 2.2 Back (FastAPI / Render)
**É dono de:** autenticação e autorização, regras de negócio, cálculo litúrgico, coleta e normalização de leituras (adaptadores), cache de liturgia, progresso do usuário, envio de push, jobs agendados, contrato OpenAPI.

**Não faz:** renderizar UI, guardar conteúdo estático de orações (isso é do front), SQL espalhado em rotas.

- Camadas internas: `routers` (HTTP) → `services` (regras) → `repositories` (SQL) → `models`.
- Adaptadores de fonte externa isolados em `integrations/`, todos atrás de uma interface comum, com fallback.

### 2.3 Banco (Neon / PostgreSQL)
**É dono de:** persistência, integridade (PK, FK, UNIQUE, CHECK, NOT NULL), índices, histórico via migrations.

**Não faz:** regra de negócio (sem triggers e funções com lógica). Toda mudança de estrutura passa por **Alembic**, nunca por SQL manual em produção.

### 2.4 Quem fala com quem
```
Front ──HTTPS (/api/* via proxy do Vercel)──> Back ──SQL (pooler)──> Neon
                                               └──HTTPS──> Fontes de leitura (só o Back)
```

---

## 3. Orçamento de desempenho

- JS inicial **< 150 KB gzip**; cada rota carregada sob demanda (`React.lazy`).
- LCP **< 2 s** em 4G médio; app abre do cache em **< 1 s** na 2ª visita.
- Sem bibliotecas pesadas: sem moment/lodash completos, sem UI kit grande. CSS leve (CSS Modules ou Tailwind com purge).
- Fontes: no máximo 1 família, `font-display: swap`, só os pesos usados, hospedadas no próprio domínio.
- Imagens: SVG/WebP, tamanhos fixos, `loading="lazy"`.
- Back: resposta de `/liturgia/hoje` **< 100 ms** quando já em cache no banco; resposta com `Cache-Control` e `ETag`.
- Medir com Lighthouse (PWA + Performance) a cada fase. Meta: ≥ 90.

**Atenção a cold start:** o Render no plano grátis hiberna; o Neon suspende quando ocioso. Por isso o front **nunca bloqueia** esperando a API, e o job diário pré-aquece e pré-carrega os dados.

---

## 4. Estrutura do repositório (monorepo)

```
oratio/
├─ PLANO.md
├─ CLAUDE.md                 # regras para o Claude Code (seção 12)
├─ content/                  # conteúdo estático (fonte única, consumido pelo front no build)
│  ├─ oracoes/*.md
│  ├─ misterios/*.json
│  ├─ novenas/*.json
│  └─ ritos/*.md
├─ web/                      # FRONT
│  ├─ src/
│  │  ├─ app/                # rotas, layout, providers
│  │  ├─ features/           # hoje, terco, novenas, oracoes, ritos, reflexoes, conta
│  │  ├─ shared/             # ui, hooks, utils
│  │  ├─ api/                # cliente + tipos gerados do OpenAPI
│  │  └─ offline/            # storage local, fila de sincronização
│  ├─ public/                # ícones, manifest
│  └─ vite.config.ts
├─ api/                      # BACK
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/               # config, segurança, logging
│  │  ├─ routers/            # auth, liturgia, usuario, push, health
│  │  ├─ services/           # regras de negócio
│  │  ├─ repositories/       # acesso a dados
│  │  ├─ models/             # SQLAlchemy
│  │  ├─ schemas/            # Pydantic (contrato)
│  │  ├─ integrations/       # fontes de leitura (adaptadores)
│  │  └─ jobs/               # tarefas agendadas
│  ├─ migrations/            # Alembic
│  ├─ tests/
│  └─ pyproject.toml
└─ .github/workflows/        # CI
```

---

## 5. Stack e bibliotecas

### Front
- React 18+, TypeScript, Vite, `vite-plugin-pwa` (Workbox).
- React Router (rotas com lazy load).
- TanStack Query (cache e stale-while-revalidate) com persistência local.
- `idb-keyval` ou Dexie para IndexedDB (progresso offline e fila de sincronização).
- `openapi-typescript` para gerar tipos da API.
- Vitest + Testing Library; Playwright para o fluxo principal.

### Back
- Python 3.12+, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`.
- SQLAlchemy 2 (async) + `asyncpg`, Alembic.
- `argon2-cffi` (senha), `PyJWT` (tokens), login Google via OAuth (ID token).
- `httpx` (async) para fontes externas, com timeout e retry.
- `pywebpush` para notificações.
- Cálculo litúrgico: `romcal` (Python, versão 4 em beta, **validar antes de adotar**) ou a lib `daily-liturgy-multilingual`; manter o cálculo atrás de uma interface própria para trocar sem dor.
- Pytest, Ruff, mypy.

### Banco
- Neon (Postgres). Usar a **string de conexão com pooler** na API. Com pooler, desativar o cache de prepared statements do `asyncpg` (`statement_cache_size=0`).
- Uma branch Neon para dev/preview e outra para produção.

---

## 6. Autenticação

- E-mail + senha (argon2) e "Entrar com Google".
- Access token curto (JWT, ~15 min) + refresh token rotativo em cookie `httpOnly`, `Secure`, `SameSite=Lax`.
- **Proxy no Vercel:** `rewrites` de `/api/*` para a URL do Render. Assim o navegador fala na mesma origem (evita problemas de cookie entre domínios, principalmente no Safari/iPhone).
- Rotas públicas: `/liturgia/hoje`, `/liturgia/{data}`, `/health`. Rotas de usuário exigem login.
- O app abre e funciona offline mesmo deslogado na sessão corrente; sincroniza ao voltar a rede.
- Rate limit em login e cadastro. CORS restrito ao domínio do front.

---

## 7. Modelo de dados (Neon)

| Tabela | Campos principais | Observações |
|---|---|---|
| `users` | id (uuid), email (único), password_hash (nulo se só Google), google_sub, name, created_at | |
| `refresh_tokens` | id, user_id, token_hash, expires_at, revoked_at | rotação |
| `user_settings` | user_id (PK), theme, font_scale, notify_time, timezone, rite_prefs (jsonb) | |
| `liturgical_days` | date (PK), season, week, color, celebration, rank, cycle_sunday, cycle_weekday, source, fetched_at | calculado |
| `readings` | id, date (FK), kind (1a, salmo, 2a, aclamacao, evangelho), reference, title, text, source | cache das fontes |
| `novena_progress` | id, user_id, novena_slug, started_on, current_day, completed_at | `novena_slug` aponta para `content/` |
| `rosary_log` | id, user_id, date, mystery_set, completed | base para sequência de dias |
| `favorites` | user_id, item_type, item_slug, created_at | PK composta |
| `intentions` | id, user_id, text, created_at, answered_at | |
| `push_subscriptions` | id, user_id, endpoint (único), p256dh, auth, created_at | |

Regras: chaves e restrições no banco; índices em `readings(date)`, `rosary_log(user_id, date)`, `novena_progress(user_id)`; tudo em UTC, exibição no fuso do usuário.

---

## 8. API (contrato inicial)

| Método e rota | Auth | Função |
|---|---|---|
| `GET /health` | não | status e aquecimento |
| `POST /auth/register`, `/login`, `/refresh`, `/logout`, `/google` | não | sessão |
| `GET /me` | sim | perfil e preferências |
| `PATCH /me/settings` | sim | atualizar preferências |
| `GET /liturgia/hoje` | não | dia litúrgico + leituras |
| `GET /liturgia/{AAAA-MM-DD}` | não | idem para outra data |
| `GET /liturgia/semana?de=...` | não | pré-carga para offline |
| `GET/PUT /me/novenas` | sim | progresso de novenas |
| `POST /me/rosario` | sim | registrar terço do dia |
| `GET/POST/DELETE /me/favoritos` | sim | favoritos |
| `GET/POST/PATCH/DELETE /me/intencoes` | sim | intenções |
| `POST/DELETE /push/subscribe` | sim | assinatura de push |

Resposta de `/liturgia/hoje` traz sempre `season`, `color`, `celebration` (mesmo se as leituras falharem) e `readings` (pode vir vazio com `status: "partial"`).

---

## 9. Fontes de leitura (só o back acessa)

Fontes públicas e **não oficiais**, usadas para uso pessoal. Podem mudar ou cair a qualquer momento.

1. **API pública `liturgia.up.railway.app`** (texto da CNBB): antífonas, orações, leituras, salmo e evangelho.
2. **API das Edições CNBB** (`api-liturgia.edicoescnbb.com.br/contents/in/date/{AAAA-MM-DD}`): não documentada; cobre só a Liturgia da Palavra.
3. **Canção Nova** (via `daily-liturgy-multilingual` ou scraper próprio).
4. **Plano B:** só as referências do dia + Bíblia de uso livre (ex.: `por_bsl`, Bíblia Portuguesa Mundial).

Repositórios de referência: `JosueSantos/api_liturgia_diaria`, `alexandrejunqueira/liturgia-diaria`, `liturgiasaoperegrino-gif/montesenario`, `soaresfellipe/api-liturgia-ptbr`, `vicenteke/daily-liturgy-multilingual`, `OtavioXimarelli/Evangelizae` (referência de produto: terço guiado e offline).

Regras de integração:
- Interface única `LiturgySource` com `fetch(date) -> LiturgyDay`; cada fonte é um adaptador.
- Ordem de tentativa com fallback; timeout curto (~5 s) e 1 a 2 retries com backoff.
- **Job diário** (Render Cron) busca os próximos 7 a 14 dias e grava em `liturgical_days` e `readings`. Requisição de usuário **nunca** dispara coleta externa se o dado já está no banco.
- Registrar a fonte usada (`source`) e exibir créditos no app ("Texto: CNBB, via ...").
- Se nada estiver disponível: mostrar tempo/cor/celebração calculados e o aviso de leituras indisponíveis.
- Texto litúrgico da CNBB tem direitos autorais. Para uso pessoal é ok; **não publicar o app** nem abrir o cache ao público sem licença.

---

### 9.1 Catálogo de APIs e fontes de dados

Legenda: ✅ confirmado na documentação do repositório · ⚠️ parcial · ❓ não confirmado (testar antes de codar).
**Nenhuma rota abaixo foi testada ao vivo ainda.** O primeiro passo da implementação é o "spike" da seção 9.2.

#### A) Leituras da Missa (texto CNBB)

| # | Fonte | Rota / acesso | O que traz | Status |
|---|---|---|---|---|
| 1 | **Edições CNBB** | `GET https://api-liturgia.edicoescnbb.com.br/contents/in/date/{AAAA-MM-DD}` | Liturgia da Palavra (leituras, salmo, evangelho). **Sem** antífona de entrada nem coleta. Sem headers especiais; um `GET` simples basta | ✅ rota · ❓ formato do JSON · ❓ resposta para data inexistente (404?) · não documentada, pode mudar |
| 2 | **Canção Nova** via lib `daily-liturgy-multilingual` | `pip install -e .` a partir do repositório; `get_daily_liturgy(date, "pt-br")`; origem: `liturgia.cancaonova.com/pb/` | Objeto com `season`, `week`, `color`, `celebrations[{name, rank}]`, `readings[{type, citation, content, alternatives}]`, `source_url`. Datas passadas e alguns meses à frente. Erros: `UnsupportedLocaleError`, `LiturgyNotAvailableError` | ✅ uso e campos (é scraping, depende do HTML do site) |
| 3 | **API Canção Nova (fork `soaresfellipe/api-liturgia-ptbr`)** | `GET /` e `GET /health`; sem parâmetros documentados; origem Canção Nova | `today.{date_string, date, color, entry_title}` e `readings.{first_reading, psalm, gospel, second_reading}`; leituras com `title, head, text, footer, footer_response, all_html`; salmo com `response`, `content_psalm[]`. Em falha sem cache: HTTP 502 `{"error":"upstream_unavailable"}` | ✅ formato · ⚠️ a URL hospedada (`api-liturgia-diaria.vercel.app`) é do repositório original, não deste fork. **Não depender dela**: usar como referência para escrever o adaptador próprio |
| 4 | **`liturgia.up.railway.app`** | só o domínio base é conhecido; o CLI aceita seções `leituras`, `salmo`, `evangelho`, `oracoes`, `antifonas` e datas em vários formatos | Leituras, salmo, evangelho, orações e antífonas, com cor litúrgica | ⚠️ domínio · ❓ rotas, parâmetros e JSON (inspecionar `src/` do repositório `alexandrejunqueira/liturgia-diaria` ou o DevTools) |
| 5 | **Nova Aliança** (`novaalianca.com.br`) | só o domínio é citado | Única fonte citada para **antífona de entrada** e **coleta**; só publica perto da data | ⚠️ domínio · ❓ tudo o mais (scraping) |
| 6 | `JosueSantos/api_liturgia_diaria` | publicada em `api-liturgia-diaria.vercel.app` (segundo o repositório) | leituras | ❓ rotas e formato |

**Ordem recomendada:** (1) Edições CNBB -> (2) Canção Nova (lib) -> (4) railway -> plano B (só referências + Bíblia).
Para **antífona de entrada e coleta**, só a Nova Aliança foi citada; tratar como extra opcional (fase 8).

#### B) Calendário litúrgico (tempo, cor, celebração)

| Fonte | Observação | Status |
|---|---|---|
| Campos `season`, `week`, `color`, `celebrations` da lib `daily-liturgy-multilingual` | Cor: verde, roxo, branco, vermelho, rosa ou preto; `rank`: solenidade, festa, memória, memória facultativa | ✅ |
| `romcal` (PyPI, v4 beta) | Cálculo local, sem rede; núcleo em Rust com bindings Python | ✅ existe · ⚠️ beta · ❓ calendário do Brasil |
| `Liturgical-Calendar/LiturgicalCalendarAPI` | API do Calendário Romano Geral em JSON/XML/ICS, com testes que validam os dados de 1970 até 25 anos à frente | ✅ existe · ❓ suporte ao calendário do Brasil e idioma pt |
| Church Calendar API (baseada em `calendarium-romanum`, Ruby) | API JSON somente leitura | ⚠️ catálogo público indica sem HTTPS; evitar |

**Decisão:** o cálculo litúrgico roda **no back** (lib local, sem rede). As APIs acima servem para **conferir** os resultados nos testes, não como dependência em produção.

#### C) Santo do dia

Não encontrei uma API pública em português com biografias que valha como dependência.
- `livesofthesaintscalendar.com`: é **ortodoxo** e exige chave. Não serve.
- Plugin "Santo do Dia" do WordPress atualiza diariamente a partir de `catolicoapp.com`: indica uma fonte, mas **sem API documentada**.
- `latinprayer.org` publica um "Saints API" com JSON, mas só foi confirmado em latim, inglês e alemão. ❓ português.
- Livros como "Um santo para cada dia" (Paulus) têm direitos autorais. Não copiar.

**Decisão:** nome do santo e grau da celebração vêm do **calendário** (campo `celebrations`). A biografia curta fica em `content/santos/` (texto próprio, escrito por você ou gerado e revisado), cobrindo primeiro as ~180 celebrações do calendário romano.

#### D) Bíblia (referências, plano B e leitura livre)

| Fonte | Rota | Observação | Status |
|---|---|---|---|
| **A Bíblia Digital** | `/versions`, `/books`, `/verses/{versão}/{livro}/{capítulo}` | JSON; exige **token gratuito** (header `Authorization: Bearer`). Boa cobertura de versões em português | ✅ rotas · ❓ quais versões; provavelmente de cânon protestante |
| **Free Use Bible API** | JSON; tradução `por_bsl` (Bíblia Portuguesa Mundial) | Mais de 1000 traduções; usada pelo PodPadre | ✅ existe · ❓ cânon completo católico |
| `devocionario/matosSoaresBibliaApi` | API Flask | **Vulgata Sisto-Clementina** traduzida pelo Pe. Matos Soares (1956); dados em CSV. É católica | ✅ · ❓ licença do texto |
| `wesleycsj/BibliaJSON` | arquivos JSON por livro | NVI, ACF e AA (cânon protestante) | ✅ |
| `bible-api.com` | `GET /{referência}?translation=` | Pede para **não** baixar a Bíblia inteira; removeu a tradução Almeida em nov/2026; sem garantias | ✅ · evitar como dependência |

**Decisão:** não chamar API bíblica em tempo de execução. Baixar **uma vez** um texto com licença clara para `content/biblia/` (JSON por livro) e servir daí. Escolher a tradução depois de checar a licença e se inclui os livros deuterocanônicos.

#### E) Orações, terço, novenas, ritos

Não há API. É conteúdo próprio em `content/` (seção 11).

### 9.2 Spike obrigatório (antes da Fase 3)

Objetivo: transformar "❓" em fatos. No seu computador (VS Code), com `curl` ou o DevTools:

- [ ] Chamar a rota das Edições CNBB para 3 datas (dia comum, domingo, solenidade) e salvar o JSON em `api/tests/fixtures/cnbb_*.json`
- [ ] Testar uma data inexistente e uma data muito futura (qual status e corpo?)
- [ ] Descobrir as rotas e o JSON de `liturgia.up.railway.app` (ler `src/` do repositório do CLI ou o DevTools)
- [ ] Rodar `get_daily_liturgy(date, "pt-br")` e salvar a saída
- [ ] Comparar texto, cor e celebração das 3 fontes para as mesmas datas
- [ ] Medir tempo de resposta e confirmar se há limite de requisições
- [ ] Decidir a ordem final dos adaptadores e escrever os **modelos Pydantic internos** (`LiturgyDay`, `Reading`) a partir dos fixtures
- [ ] Testar se `romcal` cobre o calendário do Brasil (Aparecida em 12/out, Corpus Christi etc.)

## 10. Cálculo litúrgico (no back)

- Entradas: data. Saídas: tempo litúrgico (Advento, Natal, Tempo Comum, Quaresma, Tríduo, Páscoa), semana, cor (verde, roxo, branco, vermelho, rosa), celebração/rank (solenidade, festa, memória), ciclo dominical (A/B/C) e ferial (I/II).
- Calendário do **Brasil** precisa de camada própria sobre o calendário romano (ex.: Nossa Senhora Aparecida em 12/out; verificar outras solenidades/festas nacionais e a transferência de datas como Epifania e Ascensão).
- Tabela de testes com datas conhecidas (Páscoa, Cinzas, Pentecostes, Advento, Natal, Aparecida) para validar a lib escolhida.
- O front tem **fallback local simples** (cor/tempo do dia) para o caso de API e cache ausentes? Decisão: **não**; o back é o único dono do cálculo. Offline, o front usa o último dia/semana em cache.

---

## 11. Conteúdo estático (`content/`)

- Orações: Pai-Nosso, Ave-Maria, Glória, Credo, Salve Rainha, Angelus, Regina Caeli, ladainhas, orações da manhã e da noite, Ato de Contrição, Anjo da Guarda, Via Sacra.
- **Terço:** mistérios por dia — Seg e Sáb: Gozosos; Ter e Sex: Dolorosos; Qua e Dom: Gloriosos; Qui: Luminosos. Cada mistério com meditação curta (texto próprio). Máquina de estados no front (contas, dezenas, pai-nosso/ave-marias/glória) com retomada.
- **Novenas:** Espírito Santo (Pentecostes), Natal, Nossa Senhora Aparecida, Sagrado Coração, São José, Santa Terezinha etc. Cada uma com 9 dias de texto; datas de início sugeridas calculadas pelo back.
- **Ritos:** ordinário da Missa, Liturgia das Horas, adoração ao Santíssimo, exame de consciência/confissão, Via Sacra.
  - **Liturgia das Horas:** as fontes de leitura acima **não cobrem**. Precisa de fonte própria ou licenciada. Item de pesquisa na fase 8; não bloqueia o MVP.
- **Reflexões/sermões:** só conteúdo próprio ou com autorização do autor.
- Formato: Markdown com frontmatter (`slug`, `titulo`, `categoria`, `versao`); um script valida o frontmatter no build.
- Revisar textos de oração contra fontes oficiais antes de publicar.

---

## 12. Regras para o Claude Code (`CLAUDE.md`)

Copie para o `CLAUDE.md` da raiz:

```
# Oratio — regras de trabalho
- Leia PLANO.md antes de qualquer tarefa.
- Respeite a separação: front (UI/offline), back (regra/dados/fontes), banco (persistência).
- Back: router -> service -> repository. Nada de SQL em router.
- Migrations só via Alembic. Nunca alterar o banco na mão.
- Tipos do front vêm do OpenAPI (npm run gen:api). Não escrever tipos de API à mão.
- O front nunca chama fontes externas de leitura.
- Respeitar o orçamento de desempenho da seção 3; não adicionar dependências pesadas sem justificar.
- Segredos só em variáveis de ambiente; nunca no repositório.
- Cada mudança com teste. Rodar lint, tipos e testes antes de concluir.
- Idioma da interface e do conteúdo: português do Brasil.
```

---

## 13. Variáveis de ambiente

**Back (Render):** `DATABASE_URL` (pooler Neon), `JWT_SECRET`, `JWT_ACCESS_MIN`, `REFRESH_DAYS`, `GOOGLE_CLIENT_ID`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `CORS_ORIGINS`, `LITURGY_SOURCES` (ordem), `ENV`.

**Front (Vercel):** `VITE_GOOGLE_CLIENT_ID`, `VITE_VAPID_PUBLIC_KEY`, `VITE_API_BASE` (`/api`).

Nunca versionar `.env`; manter um `.env.example` sem segredos.

---

## 14. PWA

- `manifest.webmanifest`: nome "Oratio", ícones 192/512 (inclusive maskable), `display: standalone`, cor de tema e de fundo, `start_url: /`, idioma `pt-BR`.
- Service Worker (Workbox): pré-cache do app shell e do `content/`; `StaleWhileRevalidate` para `/api/liturgia/*`; `NetworkOnly` para `/auth/*`.
- Tela de "sem conexão" amigável; fila de sincronização para ações offline (registrar terço, avançar novena).
- Instalação: botão "Instalar" no Android; instrução "Adicionar à Tela de Início" no iPhone.
- **iPhone:** push só funciona com o app instalado (iOS 16.4+). Tratar isso na tela de lembretes.
- `Wake Lock` na tela do terço; tela cheia; tema claro, escuro e sépia; tamanho de fonte ajustável.
- Notificações: lembrete diário por Web Push (VAPID), enviado por job do Render conforme `notify_time` do usuário.

---

## 15. Deploy

1. **Neon:** criar projeto, branch `main` (produção) e `dev`; copiar connection string com pooler.
2. **Render:** serviço web para `api/` (build: `pip install .`; start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`); comando de release `alembic upgrade head`; Cron Job para o job diário e para o envio de push; health check em `/health`.
3. **Vercel:** projeto apontando para `web/`; configurar `rewrites` de `/api/*` para o Render; variáveis de ambiente.
4. **Domínio** (opcional) e HTTPS (já vem nos serviços).
5. **Cold start:** opcional, um ping externo a `/health` a cada ~10 min para manter o Render acordado (dentro dos limites do plano).

---

## 16. Fases e checklist

### Fase 0 — Preparação
- [ ] Criar repositório (monorepo) e este `PLANO.md` + `CLAUDE.md`
- [ ] Criar projetos no Neon, Render e Vercel
- [ ] Configurar VS Code (ESLint, Prettier, Ruff, Python, Tailwind se usar) e Claude Code

### Fase 1 — Fundação
- [ ] `web/`: Vite + React + TS, rotas, layout, tema, PWA instalável
- [ ] `api/`: FastAPI, config, `/health`, logging, CORS
- [ ] Alembic + primeira migration (`users`, `user_settings`, `refresh_tokens`)
- [ ] Proxy `/api` no Vercel
- [ ] CI (lint, tipos, testes) e deploys automáticos
- [ ] Geração de tipos OpenAPI -> TS

### Fase 2 — Login
- [ ] Cadastro, login, refresh, logout (e-mail/senha)
- [ ] Login com Google
- [ ] Telas de entrar/cadastrar, rota protegida, preferências

### Fase 3 — Calendário e "Hoje"
- [ ] **Spike das fontes (seção 9.2) concluído, com fixtures salvos**
- [ ] Cálculo litúrgico (lib + camada Brasil) com testes de datas
- [ ] Tabelas `liturgical_days`, endpoints `/liturgia/*`
- [ ] Tela "Hoje": data, tempo, semana, cor aplicada ao tema, celebração, santo do dia
- [ ] Cache offline do dia/semana

### Fase 4 — Leituras
- [ ] Interface `LiturgySource` + adaptadores + fallback
- [ ] Tabela `readings`, job diário de pré-carga
- [ ] Tela de leituras (1ª, salmo, 2ª, aclamação, evangelho) e créditos da fonte
- [ ] Tratamento de falha parcial

### Fase 5 — Terço e orações (MVP utilizável)
- [ ] Conteúdo em `content/` + validação de frontmatter
- [ ] Biblioteca de orações com busca e favoritos
- [ ] Terço guiado (mistério do dia, contador, retomada, tela cheia)
- [ ] `rosary_log` e sequência de dias
- [ ] Lighthouse PWA/Performance ≥ 90

### Fase 6 — Novenas e lembretes
- [ ] Catálogo de novenas e progresso (`novena_progress`)
- [ ] Datas sugeridas calculadas no back
- [ ] Web Push (assinatura, envio, horário do usuário)
- [ ] Fila de sincronização offline

### Fase 7 — Ritos
- [ ] Ordinário da Missa, adoração, confissão, Via Sacra
- [ ] Intenções de oração

### Fase 8 — Liturgia das Horas e reflexões
- [ ] Pesquisar fonte de texto para a Liturgia das Horas em português
- [ ] Implementar Laudes, Vésperas, Completas (e demais horas, se houver fonte)
- [ ] Reflexões/sermões com conteúdo próprio ou autorizado

### Fase 9 — Acabamento
- [ ] Acessibilidade (contraste, leitor de tela, fonte ajustável)
- [ ] Exportar e excluir meus dados
- [ ] Testes de ponta a ponta do fluxo principal (Playwright)
- [ ] Revisão de segurança (rate limit, headers, segredos)

---

## 17. Riscos e decisões em aberto

| Item | Risco | Mitigação |
|---|---|---|
| Fontes de leitura não oficiais | Quebram ou mudam sem aviso | Adaptadores, fallback, cache de 7-14 dias, plano B |
| Direitos de autor (CNBB) | Uso público exigiria licença | Manter uso pessoal; créditos; sem exposição pública do cache |
| `romcal` v4 em beta | API pode mudar | Camada de abstração + testes de datas |
| Liturgia das Horas | Sem fonte aberta conhecida | Deixar para a fase 8, pesquisar antes |
| Cold start (Render/Neon) | Primeira chamada lenta | Offline primeiro, SWR, job de pré-carga, ping opcional |
| Push no iPhone | Só com app instalado | Orientar na UI |
| Cookies entre domínios | Falha de sessão no Safari | Proxy `/api` no Vercel (mesma origem) |

Decisões a confirmar durante o desenvolvimento:
- [ ] CSS: Tailwind ou CSS Modules?
- [ ] Login Google no MVP ou logo depois do e-mail/senha?
- [ ] Qual fonte de leitura como principal (testar as três e medir estabilidade)?
- [ ] Domínio próprio?

---

## 18. Definição de pronto (para cada fase)

- Funciona no celular (Android e iPhone) instalado como PWA.
- Funciona offline no que foi prometido para a fase.
- Testes passam, sem erros de lint e de tipos.
- Orçamento de desempenho respeitado.
- Responsabilidades respeitadas (nada de lógica fora da sua camada).
- Deploy automático funcionando.