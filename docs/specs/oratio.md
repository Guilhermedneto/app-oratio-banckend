# Oratio — PWA de oração diária

## Objective
Oratio é um app PWA católico em português do Brasil para rotinas diárias de oração: liturgia do dia (tempo, cor, celebração, leituras), terço guiado, biblioteca de orações, novenas, ritos, intenções e lembretes. Uso pessoal, com login. Deve ser moderno, rápido, funcionar offline e ter aparência e comportamento de app nativo de iPhone (iOS Human Interface Guidelines). A fonte de verdade de arquitetura é `plano.md`; este spec define o escopo da entrega: **todas as fases 0–9 do plano, construídas e verificadas localmente** (sem depender de contas Neon/Render/Vercel, chaves Google/VAPID ou fontes externas reais).

## Requirements

### Must Have

**Estrutura e arquitetura (plano §2, §4)**
- O repositório deve ser um monorepo com `content/`, `web/`, `api/`, `.github/workflows/`, `CLAUDE.md` (regras da §12 do plano) e `.env.example` (sem segredos).
- Front: React 18 + TypeScript + Vite + `vite-plugin-pwa`, React Router com rotas `React.lazy`, TanStack Query com persistência local, IndexedDB (idb-keyval ou Dexie) para dados offline.
- Back: Python 3.12 + FastAPI, Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic, camadas `routers → services → repositories → models`; nenhum SQL em routers; integrações externas só em `integrations/`.
- O front não deve chamar fontes externas de leitura nem calcular calendário litúrgico.
- Tipos da API no front devem ser gerados do OpenAPI (`npm run gen:api`); não deve haver tipos de API escritos à mão.
- Estilo: CSS Modules (sem Tailwind, sem UI kit).
- Toda mudança de esquema deve ser feita por migration Alembic; o banco não deve conter triggers/funções com regra de negócio.

**Interface estilo iPhone**
- Navegação por tab bar inferior com 5 abas: Hoje, Terço, Orações, Novenas, Mais (Mais contém Ritos, Liturgia das Horas, Reflexões, Intenções, Favoritos, Conta/Ajustes).
- Large titles que colapsam ao rolar, listas agrupadas (inset grouped), sheets modais, botões e controles com aparência iOS, cantos arredondados, respeito a `safe-area-inset-*`, fonte do sistema (`-apple-system`/SF), transições de navegação tipo push, feedback de toque (estado pressed), sem hover-only.
- Temas claro, escuro e sépia; tema inicial segue `prefers-color-scheme`; tamanho de fonte ajustável (escala salva em `user_settings.font_scale` e localmente).
- A cor litúrgica do dia (verde, roxo, branco, vermelho, rosa) deve ser aplicada como cor de destaque (accent) do app na tela Hoje.
- Idioma de toda a interface e conteúdo: pt-BR.

**PWA (plano §14)**
- `manifest.webmanifest` com nome "Oratio", ícones 192/512 incluindo maskable, `display: standalone`, `start_url: /`, `lang: pt-BR`, cores de tema/fundo.
- Service Worker (Workbox): pré-cache do app shell e do `content/`; `StaleWhileRevalidate` para `/api/liturgia/*`; `NetworkOnly` para `/auth/*`.
- Tela amigável de "sem conexão"; fila de sincronização offline para registrar terço e avançar novena, reenviada quando a rede voltar.
- Android: botão "Instalar" (evento `beforeinstallprompt`); iPhone/Safari: instrução "Adicionar à Tela de Início". A tela de lembretes deve informar que push no iPhone exige app instalado (iOS 16.4+).
- `Wake Lock` ativo na tela do terço (quando suportado); modo tela cheia no terço.
- Stale-while-revalidate: o app deve abrir com o último dado salvo e nunca bloquear esperando a API.

**Orçamento de desempenho (plano §3)**
- JS inicial < 150 KB gzip; cada rota carregada sob demanda.
- No máximo 1 família de fonte hospedada localmente (ou fonte do sistema), `font-display: swap`; imagens em SVG/WebP, `loading="lazy"`.
- Sem moment, lodash completo ou UI kit.
- `GET /liturgia/hoje` < 100 ms quando já em cache no banco, com `Cache-Control` e `ETag` (e resposta 304 para `If-None-Match` igual).
- Lighthouse PWA e Performance ≥ 90 (medido em build de produção local).

**Autenticação (plano §6)**
- `POST /auth/register`, `/login`, `/refresh`, `/logout`, `/google`.
- Senhas com argon2; access token JWT (~15 min); refresh token rotativo, guardado com hash no banco (`refresh_tokens`), entregue em cookie `httpOnly`, `Secure` (exceto em dev local), `SameSite=Lax`; refresh reutilizado/revogado deve ser rejeitado.
- Login Google por ID token; o botão só deve aparecer quando `VITE_GOOGLE_CLIENT_ID` estiver definido; o endpoint deve responder erro claro se `GOOGLE_CLIENT_ID` não estiver configurado.
- Rate limit em login e cadastro; CORS restrito a `CORS_ORIGINS`.
- Rotas públicas: `/health`, `/liturgia/hoje`, `/liturgia/{AAAA-MM-DD}`, `/liturgia/semana`. Demais rotas de usuário exigem login (401 sem token).
- O app deve abrir e funcionar offline mesmo deslogado na sessão corrente (conteúdo estático, terço, orações); sincroniza ao reconectar/logar.
- Config de dev: proxy de `/api/*` no Vite; para produção, `vercel.json` com `rewrites` de `/api/*` para a URL do Render.

**Banco (plano §7)**
- Tabelas: `users`, `refresh_tokens`, `user_settings`, `liturgical_days`, `readings`, `novena_progress`, `rosary_log`, `favorites`, `intentions`, `push_subscriptions`, com os campos, PK/FK/UNIQUE/CHECK/NOT NULL e índices (`readings(date)`, `rosary_log(user_id, date)`, `novena_progress(user_id)`) descritos no plano; datas/horas em UTC.
- Rodar localmente com Postgres via `docker-compose.yml`; a API deve usar `statement_cache_size=0` do asyncpg (compatível com pooler Neon).

**API (plano §8)**
- Implementar todas as rotas da tabela §8: `/health`, auth, `GET /me`, `PATCH /me/settings`, `/liturgia/hoje`, `/liturgia/{data}`, `/liturgia/semana?de=`, `GET/PUT /me/novenas`, `POST /me/rosario`, `GET/POST/DELETE /me/favoritos`, `GET/POST/PATCH/DELETE /me/intencoes`, `POST/DELETE /push/subscribe`.
- `/liturgia/hoje` deve sempre trazer `season`, `color`, `celebration`, e `readings` (vazio com `status: "partial"` se as leituras falharem).
- Contrato OpenAPI gerado pelo FastAPI.

**Liturgia e calendário (plano §9, §10)**
- Cálculo litúrgico no back, atrás de interface própria, local e sem rede: tempo (Advento, Natal, Tempo Comum, Quaresma, Tríduo, Páscoa), semana, cor, celebração/rank, ciclo dominical (A/B/C) e ferial (I/II), com camada do Brasil (ex.: Nossa Senhora Aparecida em 12/10) sobre o calendário romano. Se `romcal` não for viável, implementar cálculo próprio verificado por testes.
- Testes de datas conhecidas: Páscoa, Quarta-feira de Cinzas, Pentecostes, 1º domingo do Advento, Natal, Aparecida.
- Interface `LiturgySource` com `fetch(date) -> LiturgyDay`; adaptadores (Edições CNBB, Canção Nova, railway) atrás dela, com ordem configurável por `LITURGY_SOURCES`, timeout ~5 s, 1–2 retries com backoff e fallback entre fontes; plano B com só referências do dia.
- Como as rotas reais não foram verificadas, os adaptadores devem ser testados contra fixtures/mocks em `api/tests/fixtures/`; deve existir também um adaptador de desenvolvimento determinístico que gera leituras de exemplo claramente rotuladas como "amostra".
- Job diário (script executável, pronto para Render Cron) que busca os próximos 7–14 dias e grava em `liturgical_days` e `readings`; requisição de usuário nunca dispara coleta externa se o dado já está no banco. Um job de envio de push conforme `notify_time`.
- Registrar `source` e exibir créditos no app ("Texto: CNBB, via …"); se não houver leituras, mostrar tempo/cor/celebração e aviso de leituras indisponíveis.
- Santo do dia: nome e rank vêm do calendário; biografia curta em `content/santos/` com texto próprio, cobrindo ao menos as celebrações mais comuns, e ausência de biografia não deve quebrar a tela.

**Conteúdo estático (plano §11)**
- `content/` com Markdown (frontmatter `slug`, `titulo`, `categoria`, `versao`) e JSON, empacotado no build e carregado por rota; um script valida o frontmatter no build e falha o build se inválido.
- Orações: Pai-Nosso, Ave-Maria, Glória, Credo, Salve Rainha, Angelus, Regina Caeli, ladainhas, orações da manhã e da noite, Ato de Contrição, Anjo da Guarda, Via Sacra (textos tradicionais de domínio público/de uso comum, revisáveis).
- Terço: quatro conjuntos de mistérios (Gozosos seg/sáb, Dolorosos ter/sex, Gloriosos qua/dom, Luminosos qui), cada mistério com meditação curta própria; máquina de estados (contas, dezenas, Pai-Nosso/Ave-Marias/Glória) com contador, retomada do ponto em que parou e escolha manual do conjunto.
- Novenas: Espírito Santo, Natal, Nossa Senhora Aparecida, Sagrado Coração, São José, Santa Terezinha; 9 dias de texto cada; progresso por dia; datas de início sugeridas calculadas pelo back.
- Ritos: ordinário da Missa, adoração ao Santíssimo, exame de consciência/confissão, Via Sacra.
- Liturgia das Horas: telas de Laudes, Vésperas e Completas com esqueleto (hino, salmos, leitura breve, cântico, preces, oração final) usando apenas texto de domínio público/próprio e aviso visível de conteúdo parcial. Reflexões: textos curtos próprios.

**Funcionalidades de usuário**
- Tela Hoje: data, tempo, semana, cor aplicada, celebração, santo do dia, leituras (1ª, salmo, 2ª, aclamação, evangelho) e créditos; funciona offline com o último dia/semana em cache.
- Biblioteca de orações com busca e favoritos; favoritos sincronizados com a conta.
- `rosary_log` com sequência de dias consecutivos exibida no terço.
- Progresso de novenas (iniciar, avançar dia, concluir), local e sincronizado.
- Intenções de oração: criar, editar, marcar como atendida, excluir.
- Web Push: assinatura (VAPID), horário de lembrete configurável, fuso do usuário; botão para ativar/desativar.
- Ajustes: tema, fonte, horário e fuso do lembrete, exportar meus dados (JSON) e excluir minha conta e dados.

**Qualidade**
- Testes: pytest (cálculo litúrgico, adaptadores com fixtures, auth, rotas, repositories), Vitest + Testing Library (máquina do terço, componentes principais), Playwright (fluxo principal: abrir, terço, orar, ver Hoje offline). Ruff, mypy, ESLint, `tsc` sem erros.
- CI em `.github/workflows/` rodando lint, tipos e testes de web e api.
- Revisão de segurança: headers de segurança, rate limit, segredos só em variáveis de ambiente, nenhum segredo no repositório.
- Acessibilidade: contraste adequado, rótulos para leitor de tela, foco visível, respeito a `prefers-reduced-motion`, alvos de toque ≥ 44 px.
- Arquivos de deploy: `vercel.json` (rewrites), instruções do Render (start, release `alembic upgrade head`, crons, health) e do Neon (pooler) em `README.md`.

### Must Not (Out of Scope)
- Não deve fazer deploy real nem criar contas em Neon, Render ou Vercel.
- Não deve chamar fontes de leitura reais como requisito de teste (apenas fixtures/mocks).
- Não deve incluir texto da CNBB, Bíblia ou livros com direitos autorais copiados no repositório.
- Não deve ter lógica de negócio no banco nem no front (cálculo litúrgico fica só no back; sem fallback litúrgico local no front).
- Não deve chamar API bíblica em tempo de execução.
- Não deve incluir Tailwind, UI kit grande, moment ou lodash.
- Não deve implementar app nativo, versão desktop dedicada, multi-idioma, recursos sociais/compartilhamento público ou monetização.
- Não deve publicar o cache de leituras ao público.

## Behavior

### Happy Path
1. Usuário abre o app (PWA instalada ou no navegador); o app shell carrega do cache em < 1 s na 2ª visita e mostra a aba Hoje com o último dado salvo.
2. O front atualiza em segundo plano `/api/liturgia/hoje`; a UI atualiza tempo, cor, celebração e leituras sem bloquear.
3. Usuário cria conta ou entra (e-mail/senha ou Google); o app guarda o access token e o refresh vai em cookie.
4. Na aba Terço, o app sugere o conjunto de mistérios do dia; o usuário avança conta a conta, a tela fica acesa, e ao concluir registra `POST /me/rosario`; a sequência de dias é atualizada.
5. Em Orações, busca e abre uma oração, marca como favorita; em Novenas inicia uma novena e avança o dia.
6. Em Mais → Ajustes define tema, fonte e horário do lembrete e ativa o push.
7. Sem rede, todas as ações de conteúdo funcionam; registros de terço e novena entram na fila e sincronizam ao voltar a conexão.

### Edge Cases
| Scenario | Expected behavior |
|----------|-------------------|
| API fora do ar / cold start | Front mostra dado em cache imediatamente, sem spinner bloqueante; indica discretamente que está desatualizado |
| Fontes de leitura todas falham | `/liturgia/hoje` retorna `status: "partial"` com tempo/cor/celebração e `readings` vazio; app mostra aviso de leituras indisponíveis |
| Data sem dados no banco | Back consulta fontes uma vez, grava e responde; se falhar, responde parcial sem erro 5xx |
| Data inválida em `/liturgia/{data}` | 422 com mensagem; formato AAAA-MM-DD |
| Credenciais inválidas | 401 sem revelar se o e-mail existe |
| E-mail já cadastrado | 409 |
| Muitas tentativas de login/cadastro | 429 |
| Access token expirado | Front chama `/auth/refresh` uma vez e repete a requisição; se falhar, volta para tela de entrar sem perder dados locais |
| Refresh token reutilizado ou revogado | 401 e sessão encerrada |
| Google login sem `GOOGLE_CLIENT_ID` | Botão oculto no front; endpoint retorna erro claro |
| Terço interrompido (fechar o app) | Ao reabrir, oferece retomar do ponto salvo |
| Mesmo dia com dois terços registrados | Conta uma vez para a sequência; ambos ficam no log |
| Ação offline repetida / reenviada | Sincronização idempotente, sem duplicar registros |
| Push não suportado ou negado | Tela de lembretes explica o motivo (inclui iPhone não instalado) e não quebra |
| Wake Lock não suportado | Terço funciona normalmente sem ele |
| Celebração sem biografia de santo | Tela mostra só nome e rank |
| Frontmatter inválido em `content/` | Build falha com mensagem indicando o arquivo |
| Exclusão de conta | Remove todos os dados do usuário e invalida tokens |

## Constraints
- Stack: React/TS/Vite (web), Python 3.12/FastAPI (api), PostgreSQL (docker-compose local; compatível com Neon pooler).
- Plataforma-alvo: iPhone (Safari, iOS 16.4+) e Android (Chrome), instalado como PWA; desktop apenas funcional.
- Desempenho: orçamento do plano §3 (JS inicial < 150 KB gzip, LCP < 2 s em 4G médio, abertura < 1 s do cache, Lighthouse ≥ 90).
- Segurança: argon2, JWT curto, refresh rotativo httpOnly, rate limit, CORS restrito, segredos em env; `.env` nunca versionado.
- Integrações externas só pelo back, atrás de `LiturgySource`; texto litúrgico da CNBB é de uso pessoal e não deve ser redistribuído.
- Variáveis de ambiente conforme plano §13.

## Definition of Done
- [ ] `docker compose up` sobe Postgres; `alembic upgrade head` cria todas as tabelas do §7 sem erro; API sobe e `GET /health` responde 200.
- [ ] Todas as rotas da §8 existem no OpenAPI e as de usuário retornam 401 sem token.
- [ ] `npm run gen:api` gera os tipos TS a partir do OpenAPI sem edição manual.
- [ ] Testes pytest, Vitest e Playwright passam; Ruff, mypy, ESLint e `tsc` sem erros; CI configurado.
- [ ] Testes de calendário passam para Páscoa, Cinzas, Pentecostes, 1º domingo do Advento, Natal e Aparecida (12/10).
- [ ] Build de produção do front: JS inicial < 150 KB gzip e Lighthouse PWA e Performance ≥ 90.
- [ ] O app é instalável (manifest + SW válidos) e, após a 1ª visita, abre e permite orações, terço e novenas com a rede desligada.
- [ ] Na tela Hoje a cor litúrgica muda o destaque do app; leituras e créditos aparecem; com fontes falhando aparece o aviso de indisponibilidade.
- [ ] Terço: conjunto correto para cada dia da semana, contador, retomada, Wake Lock, e sequência de dias após registrar.
- [ ] Cadastro, login, refresh, logout, rotas protegidas, rate limit e exclusão de conta funcionam.
- [ ] Orações com busca/favoritos, novenas com progresso, ritos, intenções, Liturgia das Horas (parcial rotulada) e reflexões estão acessíveis.
- [ ] Push: assinatura registrada e job de envio testado com mock; tela de lembretes explica a exigência do iPhone.
- [ ] Exportar dados (JSON) e excluir conta funcionam.
- [ ] Tab bar, large titles, temas claro/escuro/sépia e fonte ajustável funcionam em viewport de iPhone.
- [ ] `README.md`, `.env.example`, `CLAUDE.md`, `vercel.json` e instruções de deploy (Render/Neon) existem; nenhum segredo no repositório.
