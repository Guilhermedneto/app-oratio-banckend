# Gestão de conteúdo e comunidade de oração

## Objective
Acrescentar ao Oratio (a) um perfil **gestor**, que cadastra e administra conteúdos (oração, texto, reflexão, rito, terço) com autoria e origem, classificados por categorias existentes ou novas, e que modera a comunidade; e (b) uma **comunidade de oração**, em que usuários publicam pedidos de oração, outros marcam "orei" e comentam, todos são avisados de novos pedidos, e o autor vê mãos unidas ("🙏") subindo na tela quando rezam por ele.

## Requirements

### Must Have
**Perfis**
- A tabela de usuários deve ter o papel `user` ou `manager`. Um e-mail listado em `MANAGER_EMAILS` (variável de ambiente, separada por vírgulas) deve receber o papel `manager` ao cadastrar, entrar ou renovar a sessão.
- `GET /me` e a resposta de login devem informar o papel. Toda rota `/gestor/*` deve retornar 403 para quem não for gestor e 401 sem login.

**Conteúdo gerido**
- O gestor deve poder criar, editar, ocultar, reexibir e excluir conteúdos com: título, tipo (`oracao`, `texto`, `reflexao`, `rito`, `terco`), categoria, corpo em Markdown, autor ("quem escreveu"), origem ("de onde vem"), link da fonte (opcional).
- O gestor deve poder escolher uma categoria que já existe (as do app e as criadas por gestores) ou criar uma nova; criar categoria deve exigir nome e gerar um identificador único; excluir categoria em uso deve ser recusado com 409.
- `GET /conteudos` e `GET /categorias` devem ser públicos, mostrar só conteúdos publicados, e responder com `ETag`.
- O app deve mostrar os conteúdos gerenciados junto dos estáticos nas listas de Orações, Textos, Reflexões, Ritos e (para `terco`) na aba Terço, agrupados por categoria, e abrir cada um com autor e origem exibidos. Depois de carregados uma vez, devem aparecer offline.
- O corpo deve ser renderizado sem HTML cru.

**Pedidos de oração**
- Usuário logado deve poder publicar um pedido (1 a 1000 caracteres, texto simples), escolhendo mostrar o próprio nome ou "Anônimo".
- Usuário logado deve ver o feed de pedidos ativos (mais recentes primeiro, paginado), com contagem de "oraram" e de comentários, e saber se ele já orou.
- Usuário logado deve poder marcar "orei" (uma vez por pedido; repetir não duplica) e desmarcar, e comentar (1 a 500 caracteres).
- O autor deve poder excluir o próprio pedido e o próprio comentário. O gestor deve poder excluir qualquer pedido ou comentário (remoção definitiva da visualização, registrando quem removeu e quando).
- A criação de pedidos e comentários deve ter limite de frequência por usuário (429).
- Usuário deslogado não deve ver o feed (401).

**Avisos**
- Ao surgir um novo pedido, todos os outros usuários logados devem ver um aviso dentro do app (faixa/aviso e contador em "Mais" até abrirem a comunidade), obtido por consulta periódica (a cada 60 s e ao voltar o foco).
- O servidor deve também enviar Web Push de "novo pedido de oração" às assinaturas dos usuários com a opção `notify_community` ligada (padrão ligada), exceto o autor.
- A opção `notify_community` deve poder ser alterada em Mais → Lembretes.

**Mãos unidas**
- Ao tocar "Orei", deve subir uma animação de 🙏 na tela. Ao abrir a comunidade, o autor deve ver subirem tantas 🙏 quantas novas orações o pedido recebeu desde a última visita dele (limitado a 12 por pedido), e o contador de cada pedido próprio deve mostrar o total. A animação deve respeitar `prefers-reduced-motion` (nesse caso, só o contador).

**Painel do gestor**
- Visível em Mais só para gestores: lista de conteúdos (com ocultar/excluir), formulário de criar/editar, gestão de categorias e moderação (todos os pedidos e comentários, com exclusão).

### Must Not (Out of Scope)
- Não deve haver denúncia por usuários, mensagens privadas, imagens, links clicáveis nos pedidos, nem edição de pedido depois de publicado.
- Não deve haver promoção de usuário a gestor pela interface (apenas `MANAGER_EMAILS`).
- Não deve haver terço guiado novo gerado pelo gestor: o tipo `terco` é um texto/roteiro, sem o passo a passo de contas.
- Não deve haver transmissão em tempo real (WebSocket/SSE); a atualização é por consulta periódica.
- Não deve haver publicação do feed para quem não está logado.

## Behavior

### Happy Path
1. Um e-mail em `MANAGER_EMAILS` cria conta; `/me` retorna `role: "manager"`; Mais mostra "Painel do gestor".
2. O gestor cria a categoria "Orações de cura" e cadastra uma oração com autor e origem; ela aparece em Orações, na categoria nova, para todos.
3. O usuário B publica um pedido; o usuário A recebe push (se assinou) e vê o aviso e o contador em Mais.
4. A abre a comunidade, lê o pedido, toca "Orei", vê 🙏 subindo, e comenta.
5. B abre a comunidade e vê 🙏 subindo e o contador "1 pessoa orou", com o comentário de A.
6. O gestor remove um comentário fora de conformidade; ele some para todos.

### Edge Cases
| Scenario | Expected behavior |
|----------|-------------------|
| Usuário comum chama `/gestor/*` | 403 |
| Sem login em `/comunidade/*` ou `/gestor/*` | 401 |
| Texto vazio ou acima do limite | 422 |
| Orei duas vezes no mesmo pedido | Uma só contagem; segunda chamada é idempotente |
| Desmarcar quem não orou | Sem erro, contagem inalterada |
| Excluir pedido de outro usuário (não gestor) | 403 |
| Pedido removido pelo gestor | Some do feed e dos contadores; comentários e orações deixam de aparecer |
| Excluir categoria em uso | 409 |
| Categoria nova com nome já existente | 409 |
| Conteúdo oculto | Não aparece em `GET /conteudos` |
| Corpo com HTML | Exibido como texto, nunca interpretado |
| Muitos pedidos em sequência | 429 |
| Offline na comunidade | Mostra o último feed carregado e informa que publicar, orar e comentar exigem conexão |
| Falha no envio de push | Não impede a criação do pedido; assinatura expirada (404/410) é removida |
| Reduzir movimento ativado | Sem animação; contador visível |

## Constraints
- Mesma stack e regras do projeto (router → service → repository; migrations Alembic; tipos do front gerados do OpenAPI; sem dependências pesadas).
- Textos dos pedidos e comentários são dados do usuário: renderizar como texto, escapar sempre.
- JS inicial continua < 150 KB gzip (telas novas carregadas sob demanda).

## Definition of Done
- [ ] Testes de API cobrem papéis, conteúdo gerido, categorias, pedidos, orações, comentários, moderação, limites e push
- [ ] Testes de front cobrem a animação/contadores, o feed e o painel
- [ ] Playwright cobre: gestor cria categoria e conteúdo que aparece em Orações; usuário B pede, A ora, B vê o contador; gestor remove
- [ ] Ruff, mypy, ESLint, `tsc`, build e JS inicial < 150 KB gzip
