# Roadmap — Leitura Ligeira

Leitor de leitura rápida self-hosted para a rede de casa, com dois jeitos de
ler: **Focus** (RSVP — uma palavra/chunk piscando em posição fixa) e **Flow**
(texto completo com a marca acompanhando a palavra, em formalização). Roda no
PC da casa, acessado pelos celulares via Wi-Fi como web app comum — sem
extensão de navegador, sem app nativo.

**Pivô de produto (2026-07-12):** o app deixa de ser single-user e passa a ser
**multiusuário leve da casa** — contas individuais para desempenho, progresso
e configurações por pessoa, mas a biblioteca continua sendo *da casa*
(documentos compartilhados por padrão; privados por escolha de quem sobe).

---

## Princípios de engenharia

1. **LEAN/ágil com visão de longo prazo.** Entregar o mínimo que valida a
   experiência e iterar com feedback de uso real — mas quando uma fase futura
   depende de um schema ou substrato, ele nasce *antes* de qualquer dado ser
   gravado no formato errado. Exemplo concreto: contas entram **antes** de
   progresso/sessões, para nunca migrar dados de leitura sem dono.
2. **Zero débito técnico deliberado.** Reordenar fases é preferível a
   retrabalho. Dependências entre fases ficam anotadas em cada fase ("depende
   de / desbloqueia") para que reprioritização seja segura.
3. **Decisões registradas, com data.** Toda reversão de decisão anterior é
   explícita (este arquivo é a fonte da verdade; a conversa se perde, o
   ROADMAP não).
4. **Testar ao vivo antes de subir.** Toda mudança é exercitada no navegador
   real (não só o código lido); o usuário testa e autoriza cada commit.
5. **Mobile-first.** O cliente principal é o celular na Wi-Fi de casa.
6. **Substratos que pagam duas vezes.** O painel token→DOM da navegação é o
   mesmo substrato do Flow e do karaoke de TTS. O relógio do highlight é
   plugável: hoje timer de WPM, amanhã timestamps de áudio.

---

## Estado atual (2026-07-12)

O que funciona hoje, testado em uso real:

- **Leitor RSVP (Focus):** micro-pausas por pontuação/palavra longa/parágrafo,
  WPM efetivo 100–1000 (o número do slider é throughput real), chunk 1–4 que
  não cruza fronteira de frase/parágrafo, ORP opcional (letra-âncora estilo
  Spritz), shrink-to-fit para palavras longas, tema claro/escuro, Wake Lock,
  tap-to-play, atalhos de teclado.
- **Navegação:** painel de texto completo (um `<span>` por palavra), clique em
  qualquer palavra pula para ela, palavra atual destacada com auto-scroll
  ("modo seguir" + botão de retorno), barra de transporte própria no painel,
  scrubber arrastável com marcadores de parágrafo, contador vivo de
  palavras/tempo restante. Navegação por frase nos botões rewind/forward.
- **Biblioteca:** paste de texto com dedupe por hash, título único automático,
  renomear/excluir, contagem de palavras + tempo estimado por item.
- **Infra:** FastAPI + SQLite (WAL, busy_timeout, foreign_keys), migrações
  automáticas de coluna, timestamps ISO UTC, limites de tamanho com erro
  amigável, histórico de navegação real (botão voltar do Android funciona
  entre biblioteca↔leitor), Dockerfile + compose, AGPL-3.0.

---

## Arquitetura

### Atual

- **Backend:** Python + FastAPI. **Banco:** SQLite, arquivo único, WAL.
- **Frontend:** JS puro + HTML/CSS, sem build step — o loop de timing do RSVP
  e o estado do player não precisam de framework, e pipeline de build é custo
  sem retorno nessa escala.
- **Deploy:** Docker Compose; LAN apenas; HTTP disponível para rede doméstica
  confiável e HTTPS opcional promovido para o gate R1 da release.
- Config do leitor em `localStorage` (por navegador).

### Alvo (com o pivô multiusuário)

- **Identidade com senha real (2026-07-12, decidido):** login de verdade,
  não um seletor sem senha. Escolhas concretas fechadas na 7ª rodada:
  hash com **`hashlib.pbkdf2_hmac` da stdlib** (zero dependência nova,
  adequado pra LAN de confiança; `bcrypt`/`argon2` são troca de 1 linha se um
  dia precisar), **sem exigência de complexidade** de senha. Sessão via
  **cookie assinado** (`SessionMiddleware` do Starlette — sem tabela de
  sessão, sobrevive a restart se a chave persistir); chave secreta gerada uma
  vez em `data/secret_key` (gitignored); cookie longevo (semanas) pro celular.
  **Auto-registro aberto na LAN** (qualquer um cria o próprio perfil; o
  primeiro vira admin). **Tela de login = seletor de perfil + senha
  (estilo Netflix).** **Tensão aceita:** HTTP permanece disponível para LAN
  doméstica confiável; HTTPS opcional e avisos de transporte entram no gate R1
  da Missão Release 1.0.
- **Papéis:** `users.role` (`admin` | `member`). O primeiro perfil criado no
  sistema vira `admin` automaticamente (convenção comum de bootstrap em apps
  self-hosted — proposta do agente, sem objeção esperada). Admin tem direitos
  sobre a **biblioteca da casa**; documentos **privados** continuam
  exclusivos do dono, admin não anula privacidade.
- **Permissões sobre documentos (2026-07-12, decidido):** quem
  renomeia/exclui um documento é (a) quem subiu (`owner_id`), (b) *[adiado —
  ver 7ª rodada]* qualquer pessoa explicitamente autorizada naquele documento
  (`document_permissions` — concessão granular, não é tudo-ou-nada), ou (c) o
  admin global (só para documentos `house`). Substitui o modelo antigo
  "qualquer um exclui" e o
  "só o dono" — era um dos dois extremos, ficou o meio-termo com concessão.
- **Configurações por conta, sincronizadas pelo servidor** — seguem a pessoa
  entre celular/PC, **incluindo o tema** (claro/escuro é por conta, não por
  aparelho — decidido). O cliente já deve acessar settings por um **módulo
  único de get/set** (hoje localStorage por trás); na fase de contas, só esse
  módulo muda para falar com o servidor. Sem retrabalho espalhado.
- **Biblioteca da casa:** documentos têm `visibility` (`house` | `private`) e
  `owner_id`. Padrão é `house`; privado só aparece para o dono.
- **Status de leitura por usuário (2026-07-12, decidido):** as prateleiras
  clássicas de biblioteca — **quero ler / lendo / lido / abandonado** — por
  usuário × documento, em `reading_progress.status`. Abrir um documento pela
  primeira vez muda o status pra "lendo" automaticamente; o usuário pode
  mudar manualmente a qualquer momento (marcar "lido", "abandonado", ou
  "quero ler" antes mesmo de abrir, como um favorito/wishlist).
- **TTS:** Kokoro-82M via Kokoro-FastAPI como serviço Docker na rede do stack
  local de IA (RTX 5060 Ti 8GB) — sem duplicar infra de GPU. PDF: PyMuPDF ·
  EPUB: `ebooklib` · URL: `trafilatura` (sem headless browser).

### Modelo de dados alvo

```
users:
  id, name, password_hash, role ('admin'|'member', default 'member'),
  created_at
  -- primeiro usuário criado vira 'admin' automaticamente

user_settings:                -- 1:1 com users
  user_id (unique),
  active_mode ('focus'|'flow'),          -- último modo usado
  wpm_focus, wpm_flow,                    -- WPM por modo
  chunk_focus, chunk_flow,                -- palavras-por-vez por modo
  font_focus, font_flow,                  -- fonte por modo (flash grande vs corpo de texto)
  orp_enabled,                            -- só Foco
  nav_snap_back_on_click, nav_pause_on_switch,  -- toggles remapeados p/ o modelo de modos
  theme, collect_stats,
  updated_at

documents:
  id, title, format, source_type (upload|url|paste),
  raw_text, content_hash, word_count, lang,
  owner_id (FK users, nullable p/ legado), visibility ('house'|'private'),
  created_at
  -- dedupe por content_hash passa a ser escopado ao owner (ver 7ª rodada):
  --   nunca colapsar/retornar documento de outra pessoa (vazamento de privado)

document_permissions:          -- ADIADO (7ª rodada) — não entra na Fase 4
  document_id, user_id (PK composta)   -- concessão granular além do dono/admin
  -- construir só quando houver demanda real; dono + admin cobrem o início

reading_progress:             -- funcional: continuar de onde parou + prateleira
  user_id, document_id, position,
  status ('quero_ler'|'lendo'|'lido'|'abandonado', default 'quero_ler'),
  updated_at
  (PK composta user_id+document_id — cada pessoa tem SUA posição e status)

reading_sessions:             -- estatísticas: event-log de sessões
  id, user_id, document_id, mode ('focus'|'flow'),
  started_at, ended_at, start_pointer, end_pointer,
  words_advanced, avg_wpm

generated_audio:
  document_id, voice, file_path, created_at
  (FKs com ON DELETE CASCADE; foreign_keys=ON já habilitado)
```

### Superfície de API alvo

```
POST       /login                        # verifica senha, emite cookie de sessão
POST       /logout
GET/POST   /users                        # listar perfis / criar perfil (define senha)
GET/PUT    /users/{id}/settings          # configurações da conta
POST       /documents                    # paste (depois upload/URL); aceita visibility
GET        /documents                    # biblioteca (casa + privados do usuário atual),
                                          # inclui status de leitura do usuário atual
GET        /documents/{id}
PATCH      /documents/{id}               # renomear — exige dono/admin (Fase 4)
DELETE     /documents/{id}               # excluir — exige dono/admin (Fase 4)
POST       /documents/{id}/permissions   # [ADIADO] concessão granular — fase futura
GET/PUT    /documents/{id}/progress      # posição + status do usuário atual
POST       /sessions                     # abrir sessão de leitura
PATCH      /sessions/{id}                # heartbeat / fechar
POST       /documents/{id}/audio?voice=  # gerar/retornar narração cacheada
GET        /documents/{id}/audio/{voice} # stream do áudio
```

---

## Registro de decisões (cronológico, condensado)

**2026-07-11 — fundação**
- Spec original: single-user, sem login, HTTP puro, Focus apenas, sem ORP,
  TTS não sincronizado. Vários desses foram revertidos depois (abaixo).
- Micro-pausas com pesos fixos: vírgula +0.35, fim de frase +0.9, palavra
  longa/número +0.5, parágrafo +1.2. Configurável por UI fica para o futuro.
- Dedupe por hash SHA-256 exato do texto aparado; título único com sufixo
  numérico; `created_at` UTC ISO; `Cache-Control: no-store` durante o
  desenvolvimento (revisar na fase de PWA).

**2026-07-12 — hardening e semântica (Fase 1.6)**
- **WPM é efetivo, não nominal:** delay normalizado pelo peso médio do
  documento; o número do slider é palavras/min reais. Recalibra a percepção
  de quem usava antes (nota no README).
- **rewind/forward navegam por frase** (unidade cognitiva), com semântica de
  player de música no rewind. Sempre pausam.
- **Chunk não cruza fronteira de frase/parágrafo** — chunks viram tamanho
  variável perto de pontuação (aceito).
- **ORP reativado** (revertendo o non-goal do spec) como toggle opcional.

**2026-07-12 — navegação e progresso (Fases 2–3 planejadas)**
- Feedback de uso real: navegar capítulo inteiro de EPUB era impraticável →
  painel de texto completo com clique por palavra, scrubber arrastável,
  contador vivo. Tudo implementado na Fase 2.
- Painel: clique por palavra; "fechar ao clicar" e "pausar ao abrir"
  configuráveis, ambos desligados por padrão; modo seguir com auto-scroll.
- Sessões de leitura: começam no primeiro play, terminam em fim de
  documento/saída/5 min de inatividade; heartbeat ~30s.
- Marcadores de parágrafo no scrubber: todos, sutis (validado com mockup).

**2026-07-12 — modos de leitura (3ª rodada)**
- Transporte dentro do painel (pedido do usuário ao testar) — o painel virou,
  na prática, o modo **Flow**. Reconhecido como o retorno do Focus/Flow do
  SwiftRead original que havia sido cortado.
- **Modo formal com seletor Focus/Flow** (não informal).
- **WPM separado por modo** (Flow tende a ser mais lento — olho em movimento).
- **Flow destaca o chunk inteiro** quando palavras-por-vez > 1.
- **TTS nos dois modos**: karaoke no Flow; no Focus, áudio + flash — com a
  ressalva técnica de que o flash precisará seguir o relógio do áudio
  (prosódia ≠ timer fixo), a fechar na fase de TTS.
- Sub-decisões: modos compartilham motor/ponteiro/estado de play; trocar de
  modo preserva posição; modo ativo persistido; ORP é conceito do Focus (não
  se aplica ao texto corrido do Flow).

**2026-07-12 — pivô multiusuário (4ª rodada, esta)**
- **Multiusuário leve:** contas individuais; biblioteca continua da casa,
  com opção de subir documento como **privado**.
- **Desempenho individual:** progresso, sessões e estatísticas por usuário;
  visualização individual ou da casa toda.
- **Coleta de estatísticas com opt-in/out por usuário** (liga/desliga).
- **Configurações por conta** (não mais por navegador/aparelho).
- Supersede as decisões anteriores "sem contas" e "estatísticas da casa como
  um usuário só".

**2026-07-12 — identidade, permissões e prateleiras (5ª rodada)**
- **Senha de verdade**, não seletor sem senha — mas sem exigência de
  complexidade obrigatória (ambiente doméstico). Reverte a proposta de
  "identidade leve sem segurança real".
- **Tema é por conta** (confirmado, não por aparelho).
- **Permissão granular sobre documentos:** dono, OU usuário com permissão
  explícita (`document_permissions`), OU admin global (só docs `house`) —
  não mais "qualquer um" nem "só o dono".
- **Opt-out de estatísticas confirmado:** desliga `reading_sessions`, mantém
  `reading_progress` (posição é funcionalidade, não telemetria).
- **Prateleiras clássicas de biblioteca:** quero ler / lendo / lido /
  abandonado, por usuário × documento (`reading_progress.status`).
- Fecha as questões abertas nº 1–4 da rodada anterior; a nº 5 (o que mais
  entra na sessão) fica respondida em parte pelas prateleiras — "documento
  terminado" já é coberto por `status = 'lido'`, não precisa duplicar como
  campo de sessão.

**2026-07-12 — deliberação profunda da Fase 3 (6ª rodada)**
- **Arquitetura Foco/Fluxo = região que troca, não overlay.** A área de
  leitura alterna flash (Foco) ↔ texto completo (Fluxo) pelo seletor, com
  **um único conjunto de controles compartilhados** embaixo (scrubber,
  contador, transporte, sliders). Reverte o modelo de overlay da Fase 2
  (`nav-panel` `fixed inset:0`). Motivo (visão de longo prazo/LEAN): o
  overlay duplicava o transporte (duas barras sincronizadas), escondia o
  scrubber e o contador no Flow, e exigia remendo de histórico. A região-que-
  troca elimina os três de uma vez. O motor (`rsvp.js`) já é agnóstico a
  modo — a mudança é toda de apresentação + settings.
- **"Voltar" nasce correto via histórico:** entrar no Fluxo empilha uma
  entrada; o botão voltar do celular vai Fluxo→Foco→biblioteca (exatamente a
  expectativa do usuário quando reportou o bug). Dissolve o backlog em vez de
  remendar.
- **Chunk é por modo** (`chunk_focus`/`chunk_flow`), como WPM e fonte.
- **Fonte é por modo por natureza** (`font_focus`/`font_flow`) — flash gigante
  vs corpo de texto, elementos DOM diferentes. Corrige o `font_size` único que
  estava no schema por engano.
- **Nomes traduzidos: Foco / Fluxo** (UI em português).
- Sub-decisões do agente (registradas, sem objeção esperada): módulo único de
  settings (hoje espalhados em ~6 pontos com 3 convenções — limpeza + preparo
  p/ Fase 4); ORP oculto no Fluxo; `prefers-reduced-motion` desliga o
  smooth-scroll; modo padrão = Foco; `wpm_flow` começa um pouco abaixo do
  `wpm_focus` na 1ª vez; relógio do highlight fica plugável de leve (avanço do
  ponteiro centralizado no motor) sem construir a abstração de áudio agora
  (anti-over-engineering); os dois toggles do painel viram
  `nav_snap_back_on_click` (clicar palavra no Fluxo volta pro Foco) e
  `nav_pause_on_switch`.

**2026-07-12 — deliberação profunda da Fase 4 (7ª rodada)**
- **Dois bugs latentes achados no código atual, que o pivô multiusuário
  transforma em reais** (corrigir na Fase 4): (a) o dedupe por `content_hash`
  é global → colar texto que outra pessoa salvou como **privado** devolveria
  o documento dela (vazamento) → escopar o dedupe ao próprio dono; (b) a
  unicidade de título é global → duas pessoas não teriam "Capítulo 1" sem
  sufixo esquisito → escopar ao dono (ou largar).
- **Decisões do usuário:** HTTP puro aceito inicialmente; em 2026-07-16 o
  HTTPS opcional foi promovido da Fase 11 para o gate R1 da release;
  **auto-registro aberto** na LAN (1º usuário vira admin); tela de login =
  **seletor de perfil + senha (estilo Netflix)**; **`document_permissions`
  adiado** (Fase 4 sai só com dono + admin — YAGNI, menos superfície).
- **Decisões de engenharia do agente (LEAN):** hash `pbkdf2_hmac` da stdlib
  (zero dep); sessão por cookie assinado (`SessionMiddleware`), chave em
  `data/secret_key`, cookie longevo; **módulo de settings continua síncrono**
  — carrega tudo no login pra um cache em memória (+ localStorage espelho),
  `getSetting` lê do cache, `setSetting` grava local na hora e faz PUT com
  debounce (não espalha `async`); migração: docs legados (`owner_id NULL`)
  viram `house` do 1º admin, settings do localStorage migram best-effort pra
  1ª conta naquele navegador. **Fora do escopo (YAGNI, limitações aceitas):**
  painel de admin, reset de senha por UI, rate-limiting/lockout de login.
- **Settings-ao-servidor fica junto** na Fase 4 (não adiado) — foi o motivo
  de termos construído o módulo único na Fase 3.

**2026-07-13 — deliberação profunda da Fase 5 (8ª rodada)**
- **Upsert lazy no sub-recurso (A1):** `GET /documents/{id}/progress` faz
  `INSERT OR IGNORE` ao ser chamado, criando linha com `position=0,
  status='quero_ler'` e promovendo imediatamente para `'lendo'` — apenas de
  `'quero_ler'`; status definidos pelo usuário (`'lido'`, `'abandonado'`)
  não são sobrescritos pela reabertura do documento.
- **`status='lido'` automático ao `onEnd()` (B1):** fim de documento é sinal
  inequívoco no RSVP; reversão manual disponível a qualquer momento.
- **Progresso na biblioteca (C1):** `GET /documents` enriquecido com LEFT JOIN
  em `reading_progress`; barra de % e tag de status renderizadas no frontend
  sem custo extra de query (o JOIN já era necessário para trazer o status).
- **Seletor inline de status (D1):** `<select>` por item na biblioteca permite
  mudança manual sem abrir o documento, incluindo marcar "quero ler" em docs
  nunca abertos (caso de uso de wishlist do ROADMAP).
- **`reading_sessions` inclui `updated_at`** atualizado a cada heartbeat e
  fechamento — campo necessário para a verificação de timeout de 5min
  (detectado na próxima abertura do mesmo doc, sem background task no servidor).
- **Heartbeat unificado:** um único `PATCH /sessions/{id}` salva posição e
  atualiza a sessão — sem dois requests paralelos; consistente com o padrão
  best-effort já adotado em settings.
- **`collect_stats` checado no momento de gravar** — opt-out não acumula
  nenhuma linha em `reading_sessions`; `reading_progress` continua sempre
  ativo (é funcionalidade, não telemetria).
- **`ON DELETE CASCADE`** nas FKs de ambas as tabelas para `users` e
  `documents` — sem dado órfão ao excluir usuário ou documento; consistente
  com `generated_audio` já no ROADMAP.
- Limitação aceita (nova): app morto abruptamente e reaberto em menos de 5min
  pode deixar sessão órfã aberta convivendo com a nova — detectada e fechada
  só após o timeout. Mesmo espírito das "palavras lidas podem inflar".
- **Ambas as presunções confirmadas por Samuel (2026-07-13), com desenho mais
  rico do que a pergunta binária original:**
  (a) `'abandonado'`/`'lido'` não são promovidos para `'lendo'` pela
  reabertura — **mas documentos abandonados ganham uma seção própria,
  recolhida por padrão, na biblioteca** ("Abandonados (N)"), separada da
  lista ativa para eliminar o risco de abrir um por engano. Clicar no
  título/info de um item abandonado abre um modal com três escolhas
  ("Continuar lendo" → `'lendo'`, "Quero ler" → `'quero_ler'`, "Manter
  abandonado") — **qualquer escolha permite explorar o documento**, o modal
  nunca bloqueia a entrada, só pede uma decisão consciente antes.
  (b) `<select>` aparece mesmo para docs nunca abertos, **mas com um estado
  neutro** ("— sem status —") em vez de pré-selecionar "Quero ler" — evita
  fingir que uma escolha já foi feita quando não existe linha no banco ainda.
  O valor neutro é só de exibição; nunca é gravado via `PUT`.

---

## Questões arquiteturais resolvidas

A Fase 8 não possui mais questões arquiteturais abertas. A estratégia final
combina timestamps do Kokoro, alinhamento fuzzy e reparação proporcional pela
duração real do MP3 quando a cobertura é parcial (`timestamps:null`).
*(As questões nº 1–5 da rodada anterior sobre contas/permissões/opt-out/
prateleiras foram todas fechadas em 2026-07-12 — ver "Registro de decisões"
acima e as fases 4/5 abaixo.)*

---

## Decisões Arquiteturais Recentes

**Correção Arquitetural do Modo Fluxo (Decidido em 2026-07-13 após Fase 6) —
IMPLEMENTADA E TESTADA ao vivo em 2026-07-13:**
**Problema original:** `buildFlowContent()` travava a tela por ~7s em livros grandes (ex: EPUB de 146k palavras) ao criar centenas de milhares de `<span>` síncronos.
**Solução Atual: Lazy Spanification (Virtualização Híbrida)**
- Em vez de gerar spans para cada palavra do livro inteiro de uma vez, divide-se os tokens em parágrafos e cria-se `<div>` de texto plano.
- Quando a palavra acende (`updateFlowHighlight`), encontra-se a unidade por busca binária e "spanifica" na hora.

**ATUALIZAÇÃO DE HARDENING (Auditoria de Segunda Opinião):**
A arquitetura base é correta, mas a implementação de 2026-07-13 requer os seguintes ajustes críticos (que devem ser feitos antes de avançar nas fases ou na Fase 8):
1. **Unidade Limitada (Segmento, não Parágrafo):** "Parágrafo" não tem limite de tamanho em arquivos patológicos (ex: PDF sem quebras). Mudar de `flowParagraphs` para `flowBlocks` limitando a um máximo de ~250 tokens, quebrando preferencialmente no `sentenceEnd`. Se uma unidade tiver 100k palavras, a spanificação travará a thread novamente.
2. **Proteção contra Layout Thrashing no Scroll:** O Claude Code usou um listener de scroll síncrono lendo `offsetTop`. Isso intercala leitura/escrita no DOM em todo frame, causando Layout Thrashing em mobile. **Obrigatório:** Coalescer o evento (`requestAnimationFrame`), determinar quais blocos estão visíveis sem tocar no DOM, e spanificar usando `DocumentFragment` com uma única mutação por bloco.
3. **Limpeza de Estado (Memory Leak mitigado):** Mudar para outro documento não destrói o DOM do Fluxo anterior se não for explícito. Deve-se resetar tudo (`flowFollowMode`, `scrollTop`, esvaziar arrays) ao carregar novo texto.
4. **Resumo:** Não tentar virtualização profunda agora, mas aplicar limite máximo por segmento e proteção síncrona no scroll.

*(As questões nº 1–5 da rodada anterior sobre contas/permissões/opt-out/
prateleiras foram todas fechadas em 2026-07-12 — ver "Registro de decisões"
acima e as fases 4/5 abaixo.)*

---

## Backlog imediato (resolvido pelo desenho da Fase 3)

Os dois itens de feedback abaixo deixam de ser correções pontuais e são
**dissolvidos pela arquitetura de "região que troca"** decidida na 6ª rodada:

- **[bug] Botão voltar do Android** ia pra biblioteca em vez de sair do Fluxo.
  Com o modo empilhando histórico, "voltar" vira Fluxo→Foco→biblioteca
  naturalmente — não precisa de remendo no overlay (que deixa de existir).
- **[ajuste] Controles (WPM/fonte/chunk) acessíveis no Fluxo.** Com os
  controles compartilhados embaixo da região que troca, eles já estão sempre
  visíveis nos dois modos — não é uma seção extra no painel, é o mesmo
  conjunto de controles.

---

## Fases

### Concluídas

- **[x] Fase 1 — Núcleo RSVP** *(2026-07-11)*: engine com micro-pausas,
  player, paste de texto, dedupe, Docker, README.
- **[x] Fase 1.5 — CRUD da biblioteca**: renomear/excluir com confirmação;
  correção do modal preso (`.modal[hidden]`) e dedupe por hash.
- **[x] Fase 1.6 — Hardening da fundação**: persistência de settings, Wake
  Lock, tap-to-play, histórico real, fronteiras de chunk, estado de fim, WPM
  efetivo, navegação por frase, WAL/busy_timeout, timestamps ISO, word_count,
  shrink-to-fit, limites de tamanho, melhorias de modal, colunas
  `lang`/FKs, ORP opcional + fix do encolhimento de fonte.
- **[x] Fase 2 — Navegação no texto** *(2026-07-12)*: painel de texto
  completo com clique por palavra, modo seguir, scrubber arrastável com
  marcadores, contador vivo, transporte no painel sincronizado com o leitor.

### Futuras (ordem redesenhada em 2026-07-12; dependências anotadas)

> Racional da ordem: (A) fechar o módulo de leitura enquanto é só frontend;
> (B) contas **antes** de qualquer dado por usuário ser gravado (evita
> migração de progresso órfão — a regra nº 1 dos princípios); (C) conteúdo
> depois que a fundação de dados existe (o import já nasce com visibilidade
> privado); (D) TTS quando leitura + conteúdo estão completos; (E)
> enriquecimento por cima dos dados acumulados.

#### [x] Fase 3 — Leitura completa: modos Foco/Fluxo formais *(implementada 2026-07-12, aguardando teste do usuário)*
*Depende de: nada (só frontend). Desbloqueia: TTS (substrato/relógio pronto),
sessões com campo `mode`, Fase 4 (módulo de settings).*
Desenho fechado na 6ª rodada de deliberação (ver log de decisões).

**Arquitetura — região que troca (não overlay):**
- A área de leitura é uma **região única que alterna** entre o flash (Foco) e
  o texto completo (Fluxo), controlada por um seletor **Foco / Fluxo**.
- **Um só conjunto de controles compartilhados** embaixo da região: scrubber
  com marcadores, contador vivo, transporte (rewind/play/forward), sliders.
  Acaba a duplicação das duas barras de transporte da Fase 2.
- Reestrutura o `nav-panel` (hoje `fixed inset:0`) para essa região —
  reaproveitando texto/clique-pra-pular/auto-scroll já prontos, só que como
  superfície de primeira classe, não overlay.
- Trocar de modo preserva ponteiro e estado de play (o motor não sabe de
  modo). Entrar no Fluxo **empilha histórico**; "voltar" vai Fluxo→Foco→
  biblioteca — dissolve o bug do botão voltar.

**Settings por modo (corrige o schema):**
- Módulo **único** de get/set de settings (hoje espalhado em ~6 pontos com 3
  convenções) — limpeza + ponto único para a Fase 4 redirecionar ao servidor.
- **WPM, chunk e fonte são por modo** (`*_focus` / `*_flow`); os controles são
  mode-aware (mostram e gravam o valor do modo ativo). Fonte do Fluxo alvo o
  corpo de texto; a do Foco, a palavra do flash.
- `wpm_flow` inicia um pouco abaixo do `wpm_focus` na 1ª vez (olho em
  movimento pede mais devagar).
- **ORP é exclusivo do Foco** — o toggle some/desabilita no Fluxo.

**Comportamento do Fluxo:**
- **Destaca o chunk inteiro** (as N palavras do chunk atual acesas juntas,
  marca pula de N em N) — exige expor as fronteiras do chunk do motor ao
  destaque (hoje o `onProgress` só passa o ponteiro).
- Auto-scroll de acompanhamento (modo seguir + botão de retorno) já pronto;
  respeitar `prefers-reduced-motion` (sem smooth-scroll para quem pede).
- Os dois toggles do painel viram: `nav_snap_back_on_click` (clicar numa
  palavra no Fluxo pula e volta pro Foco) e `nav_pause_on_switch`.

**Não incluído (evitar over-engineering):** a abstração de relógio de áudio do
TTS não entra aqui — mas o avanço do ponteiro fica centralizado no motor para
a Fase 8 plugar o áudio sem cirurgia. Modo padrão de novo leitor = Foco.

**Implementado e testado ao vivo no navegador** (2026-07-12): módulo único de
settings (`getSetting`/`setSetting`, prefixo `settings.`); `#rsvp-stage` e
`#flow-region` como região que troca (com `.rsvp-stage[hidden]{display:none}`
corrigido — o mesmo bug de `display` vs `[hidden]` já visto no modal); URL/
histórico com `#/read/{id}/{mode}`; botão voltar confirmado Fluxo→Foco→
biblioteca; WPM/chunk/fonte mode-aware com `wpm_flow` derivado de
`wpm_focus - 50` na primeira vez; destaque do chunk inteiro no Fluxo
confirmado com chunk=2; toggles de snap-back e pausar-ao-trocar validados;
scrubber e auto-scroll/botão-de-retorno funcionando na nova estrutura;
persistência confirmada após reload completo. Nenhum código commitado ainda
— aguardando teste e autorização do usuário.

#### [x] Fase 4 — Contas da casa (multiusuário leve, com senha) *(implementada 2026-07-12, aguardando teste do usuário)*
*Depende de: Fase 3 (módulo de settings). Desbloqueia: Fases 5, 6 (privado),
9 (stats individuais). Plano fechado na 7ª rodada de deliberação.*

**Auth e sessão:**
- Tabela `users` (`id, name` único, `password_hash`, `role`, `created_at`);
  hash com `hashlib.pbkdf2_hmac` (salt por usuário; sem dependência nova);
  sem exigência de complexidade de senha.
- **Auto-registro aberto:** a tela de login lista os perfis existentes
  (estilo Netflix) + opção "novo perfil"; toca no seu, digita a senha. O
  **primeiro perfil criado vira `admin`** automaticamente.
- `POST /login` (verifica senha) e `POST /logout`; sessão via
  `SessionMiddleware` do Starlette (cookie assinado, longevo). Chave secreta
  gerada uma vez em `data/secret_key` (gitignored). Dependência `current_user`
  do FastAPI em todos os endpoints; **401 → frontend redireciona pro login**
  (um handler global de fetch).
- Afordância visível de trocar de perfil / sair.

**Biblioteca multiusuário:**
- `documents.owner_id` + `visibility` (`house` default | `private`); modal de
  paste ganha a opção "privado". `GET /documents` = casa + privados do usuário
  atual.
- **Corrigir os dois bugs latentes (ver 7ª rodada):** dedupe por
  `content_hash` escopado ao dono (nunca retornar documento de outra pessoa);
  unicidade de título escopada ao dono.
- **Permissões (versão enxuta):** renomear/excluir exige **dono** OU **admin**
  (admin só em docs `house`; privados seguem exclusivos do dono). A concessão
  granular (`document_permissions`) fica **adiada** até ter demanda real.
- Migração: docs legados (`owner_id NULL`) viram `house` do 1º admin.

**Settings por conta:**
- `user_settings` no servidor (`GET/PUT /users/{id}/settings`, inclui tema).
- O módulo de settings da Fase 3 **continua síncrono**: no login carrega tudo
  num cache em memória (+ localStorage como espelho offline); `getSetting` lê
  do cache; `setSetting` grava local na hora e faz PUT com debounce. Settings
  atuais do localStorage migram best-effort pra 1ª conta criada no navegador.

**Fora do escopo (YAGNI — limitações aceitas, documentadas):** painel de
admin, reset de senha por UI (admin recria/redefine no banco se preciso),
rate-limiting/lockout de login. O hardening de login e o HTTPS opcional foram
promovidos para R6 e R1 da Missão Release 1.0, respectivamente.

**Implementado e testado ao vivo no navegador** (2026-07-12): backend
verificado extensivamente via curl (registro/login/logout, cookie de sessão,
bootstrap do 1º usuário como admin + backfill dos documentos legados,
dedupe por `content_hash` e unicidade de título escopados ao dono — os dois
bugs latentes confirmados corrigidos, incluindo o caso crítico de colar o
mesmo texto de um documento privado alheio: cria documento novo, não
vaza o conteúdo). Frontend testado end-to-end no browser: tela de login
estilo Netflix com lista vazia → criação do 1º perfil (virou admin,
documentos legados herdados) → biblioteca com botões renomear/excluir
visíveis (dono); documento privado criado e confirmado só visível ao dono
(`GET /documents/{id}` de outra conta retorna 404); segunda conta (`member`)
confirmada sem botões de gerenciar nos documentos da casa alheios (403 ao
tentar `PATCH` direto via API) e sem visibilidade do documento privado;
settings sincronizadas ao servidor com debounce e confirmadas isoladas por
conta (WPM alterado numa conta não vaza pra outra); logout e reautenticação
por cookie após reload confirmados; sessão inválida em qualquer fetch
autenticado confirmada redirecionando para a tela de login. Dados de teste
(2ª conta e documento privado de teste) removidos após a validação — banco
retorna ao estado real do usuário. Nenhum código commitado ainda —
aguardando teste e autorização do usuário.

#### [x] Fase 5 — Progresso, prateleiras e sessões por usuário *(implementada 2026-07-13, aguardando teste do usuário)*
*Depende de: Fase 4 (user_id). Desbloqueia: Fase 7 (busca por prateleira),
Fase 9 (dashboard), gamificação. Plano fechado na 8ª rodada de deliberação.*

**Resumo executivo:** Adiciona persistência de posição e status de leitura por
usuário×documento (`reading_progress`) e rastreamento de sessões opt-in
(`reading_sessions`). O banco recebe duas tabelas novas via `CREATE TABLE IF
NOT EXISTS` — sem migração de dado legado (contas existem antes deste dado,
conforme princípio nº 1 do ROADMAP). A biblioteca exibe status e progresso
percentual de cada item via LEFT JOIN na listagem. A posição é restaurada ao
abrir um documento e salva em quatro gatilhos: pause, troca de modo, saída da
reader-view e `visibilitychange→hidden`. Sessões só registradas se
`collect_stats = 1`; `reading_progress` é sempre ativo (funcionalidade,
não telemetria).

**Schema — tabelas novas (bloco `SCHEMA` de `database.py`):**

```
reading_progress:
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  position    INTEGER NOT NULL DEFAULT 0,
  status      TEXT    NOT NULL DEFAULT 'quero_ler',
  updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  PRIMARY KEY (user_id, document_id)
  -- índice: reading_progress(user_id) — cobre LEFT JOIN na listagem

reading_sessions:
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  mode           TEXT    NOT NULL,
  started_at     TEXT    NOT NULL,
  ended_at       TEXT,
  updated_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  start_pointer  INTEGER NOT NULL DEFAULT 0,
  end_pointer    INTEGER,
  words_advanced INTEGER,
  avg_wpm        REAL
  -- updated_at atualizado a cada heartbeat/fechamento — base do timeout de 5min
  -- índice: reading_sessions(user_id, document_id) — cobre dashboard Fase 9
```

**Novos arquivos de backend:**
- `app/routers/progress.py` — `GET` e `PUT /documents/{id}/progress`.
- `app/routers/sessions.py` — `POST /sessions` e `PATCH /sessions/{id}`.

**Modificações de backend:**
- `database.py`: dois `CREATE TABLE IF NOT EXISTS` + dois `CREATE INDEX IF
  NOT EXISTS` em `init_db()`. Nenhuma entrada nova em `MIGRATIONS`
  (tabelas novas, não colunas em tabelas existentes).
- `schemas.py`: `ProgressOut`, `ProgressUpdate`, `SessionCreate`,
  `SessionHeartbeat`, `SessionClose`; `DocumentSummary` ganha
  `progress_position: int | None` e `progress_status: str | None`.
- `documents.py` (`GET /documents`): LEFT JOIN em `reading_progress` para o
  `user_id` atual; traz `progress_position` e `progress_status` (nullable).
- `main.py`: registrar `progress.router` e `sessions.router`.

**Comportamento de `GET /documents/{id}/progress` (A1 — upsert lazy):**
1. Verifica visibilidade via `_get_visible_document` → 404 idêntico ao
   "não existe" se privado de outro (não confirma existência do privado).
2. `INSERT OR IGNORE` — cria linha com defaults se não existir.
3. `UPDATE SET status='lendo', updated_at=? WHERE status='quero_ler'` —
   só promove de `'quero_ler'`; `'lido'` e `'abandonado'` não são
   sobrescritos pela reabertura.
4. Retorna a linha atual.

**Comportamento de `PUT /documents/{id}/progress`:**
Partial update de `position` e/ou `status`; enum validado no router
(`'quero_ler'|'lendo'|'lido'|'abandonado'`, 422 para qualquer outro);
`user_id` sempre do cookie de sessão — nunca do corpo ou da URL da request.
Gatilhos no frontend: pause, troca de modo, saída da reader-view,
`visibilitychange→hidden`, `onEnd()` (com `status='lido'`).

**Comportamento de `POST /sessions` e `PATCH /sessions/{id}`:**
- `collect_stats` checado **no momento de gravar** — retorno silencioso
  `{ok: true, session_id: null}` se desligado; `reading_progress` segue ativo.
- Sessão nasce no **primeiro play** (não na abertura do documento).
- `PATCH` (heartbeat ~30s, durante play): atualiza `end_pointer`, `position`
  no `reading_progress` (unificado), `updated_at`. Um único request.
- `PATCH` (fechar): adiciona `ended_at`, `words_advanced = end_pointer -
  start_pointer`, `avg_wpm` se fornecido.
- Sessão fechada em: `onEnd()`, `showLibrary()`, troca de documento.
- Timeout de 5min: ao abrir nova sessão, fecha sessão anterior se
  `ended_at IS NULL AND updated_at < now() - 5min` — sem background task.
- Sessão verificada como pertencente ao `user_id` do cookie antes de qualquer
  escrita (404 se não for).

**Biblioteca — C1 (tag + barra de progresso) + D1 (seletor inline), com
desenho final de status confirmado em 2026-07-13:**
- `GET /documents` traz `progress_position` e `progress_status` por LEFT JOIN.
- Cada item exibe: barra de `% = round(position / word_count * 100)` (calculado
  no frontend) e tag colorida de status (⭐ Quero ler / 🔖 Lendo / ✅ Lido /
  🚫 Abandonado).
- `<select>` inline com os 4 status reais + uma opção neutra "— sem status —"
  **só de exibição** (nunca enviada via `PUT`) para docs nunca abertos
  (`progress_status = null`). `e.stopPropagation()` no `change` impede abrir
  o leitor ao trocar o status. Dispara `PUT /documents/{id}/progress`.
- **Seção "Abandonados (N)" separada, recolhida por padrão** — documentos com
  `status='abandonado'` saem da lista principal e vão para um bloco fechado
  abaixo (precisa expandir pra ver). Elimina o risco de clique acidental num
  documento já descartado.
- **Modal de confirmação ao clicar num item abandonado:** clicar no
  título/info (não no `<select>`) de um item dentro da seção recolhida abre
  um modal com três botões — "Continuar lendo" (`PUT status='lendo'`),
  "Quero ler" (`PUT status='quero_ler'`), "Manter abandonado" (nenhum PUT).
  **Todas as três opções abrem o leitor em seguida** — o modal nunca bloqueia
  a exploração, só evita que o clique promova o status silenciosamente.

**Decisões fechadas:**
- A1 (upsert lazy no sub-recurso) — mais contido que side-effect no GET do
  documento principal; sem overhead de endpoint extra vs A3.
- B1 (`status='lido'` automático ao `onEnd()`) — fim de documento é sinal
  inequívoco no RSVP; reversão manual trivial.
- C1 (tag + % na biblioteca) — JOIN já necessário; custo marginal zero.
- D1 (seletor inline) — habilita caso "quero ler antes de abrir".
- `ON DELETE CASCADE` em ambas as FKs de ambas as tabelas.
- Heartbeat unificado (posição + sessão num único `PATCH`).
- `user_id` sempre do cookie, nunca do body/URL.
- Quatro gatilhos de save de posição (pause, troca de modo, saída, visibility).
- Sessão nasce no primeiro play — abertura sem play não gera sessão.
- **(Fechado em 2026-07-13)** Seção "Abandonados" separada e recolhida por
  padrão na biblioteca, com modal de confirmação de 3 escolhas ao clicar num
  item — nenhuma escolha bloqueia a exploração do documento.
- **(Fechado em 2026-07-13)** Select de status mostra estado neutro
  ("— sem status —", só visual) para docs nunca abertos, em vez de
  pré-selecionar "Quero ler".

**Fora de escopo (YAGNI):**
- Visualização de sessões passadas — Fase 9 (dashboard).
- Filtro por prateleira na biblioteca — Fase 7.
- Anti-inflação de `words_advanced` — limitação aceita (ver abaixo).
- Conflito de posição entre dispositivos — last-write-wins, sem SLA.
- Endpoint de listagem de sessões — sem consumidor até Fase 9.

**Limitações aceitas:**
- `words_advanced` pode inflar: play sem leitura ativa e saltos de navegação
  contam como avanço — sem detecção de atenção real.
- App morto abruptamente (OOM, force-close) e reaberto em menos de 5min pode
  deixar sessão órfã aberta convivendo com a nova. Detectada e fechada só
  após o timeout de 5min na próxima abertura do mesmo documento. Sem impacto
  funcional na leitura — mesmo espírito das "palavras lidas podem inflar"
  já aceitas no ROADMAP.

**Testes previstos antes de Samuel autorizar:**
1. Restauração de posição: abrir doc, ler até N, voltar à biblioteca,
   reabrir → motor começa em N (não em 0).
2. **Teste adversarial:** conta A lê doc X até posição N → `GET
   /documents/{X}/progress` autenticado como conta B retorna `position=0`
   (linha inexistente) — nunca N.
3. **Privado + progresso:** `PUT /documents/{privado}/progress` como
   não-dono → 404 idêntico ao "documento não existe".
4. **Opt-out de coleta:** conta com `collect_stats=0` → play → zero linhas
   em `reading_sessions`; `reading_progress` funciona normalmente.
5. Status automático ao abrir: primeiro acesso ao doc → `status='lendo'`
   na resposta; `'abandonado'` pré-existente não é sobrescrito (se presunção
   confirmada).
6. `status='lido'` ao fim: chegar ao `onEnd()` → verificar no banco.
7. Seletor manual: mudar status via `<select>` → request enviado →
   status correto persistido; leitor não abre (`stopPropagation`).
8. `visibilitychange` em celular real (Android Chrome): minimizar durante
   leitura → reabrir → posição salva sem pause explícito.
9. Cascade ao deletar documento: `reading_progress` e `reading_sessions`
   somem junto (verificar no banco).
10. Cascade ao deletar usuário (direto no banco, sem endpoint de UI ainda):
    idem.
11. Barra de progresso: doc de 1.000 palavras, posição 500 → barra ~50%.
12. Doc nunca aberto: `progress_position=null` → barra oculta; select mostra
    "— sem status —" (neutro, não gravado até uma escolha real ser feita).
13. Seção "Abandonados": marcar um doc como abandonado → some da lista
    principal e aparece na seção recolhida; seção começa fechada ao carregar
    a biblioteca.
14. Modal de confirmação: clicar no título de um item abandonado → modal
    aparece com as 3 opções; cada uma abre o leitor em seguida (nenhuma
    bloqueia); "Continuar lendo" e "Quero ler" persistem o novo status via
    `PUT`, "Manter abandonado" não dispara request nenhum.

**Implementado e testado ao vivo no navegador** (2026-07-13): todos os 14
testes acima confirmados, incluindo os dois adversariais (posição de outra
conta nunca vaza via `GET /progress`; documento privado de outra conta
retorna 404 idêntico em `GET`/`PUT /progress`) e o cascade duplo (deletar
documento e deletar usuário removem `reading_progress`/`reading_sessions`
sem órfão). Upsert lazy confirmado promovendo `quero_ler`→`lendo` só na
condição certa; `abandonado`/`lido` confirmados não sobrescritos pela
reabertura. Seção "Abandonados" nativa via `<details>` (recolhida por
padrão sem JS) e modal de 3 escolhas testados nos dois branches que geram
PUT ("Continuar lendo", "Quero ler") e no que não gera nenhum ("Manter
abandonado"). Opt-out de `collect_stats` confirmado: `POST /sessions`
retorna `session_id: null` e zero linha gravada, `reading_progress`
funciona normalmente de qualquer forma. `visibilitychange→hidden`
confirmado salvando posição sem precisar de pause explícito. Uma nota de
comportamento emergente, não um bug: como toda abertura do leitor promove
`quero_ler`→`lendo` (por design), escolher "Quero ler" no modal de
abandonado e escolher "Continuar lendo" convergem para o mesmo status
`'lendo'` assim que o leitor abre — a diferença entre as duas opções dura
só a fração de segundo antes do `GET /progress` da abertura rodar. Aceito
como consequência natural de "abrir para explorar é abrir para ler".
Dados de teste (2ª conta descartável e documento privado de teste)
removidos após a validação. Nenhum código commitado ainda — aguardando
teste e autorização do usuário.

**Bug encontrado pelo Samuel em teste ao vivo (2026-07-13) e corrigido:**
`doRewind()`/`doForward()` em `app.js` chamam `engine.rewind()`/
`engine.forward()`, que pausam o motor internamente — mas os wrappers não
chamavam `saveProgress()`, então retroceder/avançar durante a leitura não
salvava a posição (só o pause explícito pelo botão salvava). Mesma causa
raiz também afetava o scrubber. Corrigido adicionando `saveProgress()` nos
três pontos (rewind, forward, `pointerup`/`pointercancel` do scrubber —
não em `pointermove`, para não gerar um PUT por frame do arrasto).

#### [x] Fase 6 — Import: arquivo + URL (+ TOC)
*Depende de: Fase 4 (visibilidade/owner no upload). Desbloqueia: TTS com
conteúdo real, Fase 7 (biblioteca cheia pede organização). Plano fechado
na 9ª rodada de deliberação (2026-07-13).*

**Resumo executivo:** Expande a adição de documentos para suportar upload de
arquivos (PDF via `pymupdf`, EPUB via `ebooklib`, TXT) e extração de texto
via URL (usando `trafilatura`). Adiciona suporte a sumário (TOC) para navegação,
exposto como um menu na barra do leitor. O TOC é mapeado em índices de token
para o motor RSVP pular com precisão.

**Schema e Migração (bloco MIGRATIONS em `database.py`):**
- A tabela `documents` ganha a coluna `toc TEXT` (armazenado como JSON nullable).
- O formato do JSON é `[{"title": "Capítulo 1", "token_index": 120}, ...]`.
- `format` e `source_type` já existem e receberão os valores corretos 
  (ex: `format='pdf'`, `source_type='upload'`).

**Novos endpoints (`app/routers/import_routes.py`):**
Para não quebrar a compatibilidade da API existente (`POST /documents` via JSON),
dois novos endpoints síncronos (rodando em thread pool via FastAPI `def`):
1. `POST /documents/upload`: aceita `multipart/form-data`.
   - Limita em `MAX_FILE_BYTES = 50 * 1024 * 1024` (50MB) em memória.
   - Extrai o texto limpo, calcula os índices de token (`len(text[:char_offset].split())`) para o TOC.
2. `POST /documents/url`: aceita JSON `{ "url": "..." }`.
   - Valida SSRF bloqueando loopback (decisão A1).
   - Usa `trafilatura.extract()` para buscar o conteúdo. Sem TOC gerado.

*Regras aplicáveis a ambos:* dedupe por `content_hash` escopado ao dono (já
existente), visibilidade (privado vs house), falham graciosamente (ex: PDF
sem texto retorna 422 legível).

**Dependências (adicionadas a `requirements.txt`):**
- `pymupdf`, `ebooklib`, `trafilatura`. HTML do EPUB parseado nativamente 
  usando `html.parser` da biblioteca padrão do Python.

**Frontend (`index.html` e `app.js`):**
- **Modal Unificado:** o botão "+ Novo texto" abre um modal remodelado com
  três abas: **Colar texto**, **Arquivo**, **URL**.
- **UI do TOC no leitor:** botão "≡ Capítulos" na topbar do leitor (Foco e 
  Fluxo), abrindo um dropdown nativo ou customizado. Ao clicar no capítulo,
  chama `engine.seekToIndex(idx)` e fecha o menu. Oculto via `hidden` se 
  o documento não tiver `toc` no seu `DocumentDetail` (caso de colagens 
  simples ou URLs sem outline).

**Fora do escopo (Limitações aceitas - YAGNI):**
- OCR em PDF escaneado (sem texto - falhará com erro claro).
- Reparação da ordem de leitura em PDFs densos de 2 colunas.
- Progress bar em streaming para o upload (bloqueia o UI com "Processando...").
- Reprocessar TOC de documentos antigos.
- Outros formatos (MOBI, AZW).

**Checklist de testes pós-implementação (para Claude Code):**
- [x] Paste: O antigo modal de "Colar texto" ainda funciona (agora como aba).
- [x] EPUB (Teste Adversarial): Clicar num capítulo no TOC precisa pular *exatamente*
      para a primeira palavra daquele capítulo no leitor (garante paridade
      na tokenização Python vs JS).
- [x] PDF grande (Proteção): Tentar subir arquivo > 50MB falha limpo.
- [x] PDF Imagem (Proteção): Upload de PDF escaneado retorna erro 422 claro.
- [x] URL com paywall/JS-only (Proteção): falha com erro 422 claro.
- [x] URL SSRF (Adversarial): URL apontando para `http://localhost:8000` ou 
      `http://127.0.0.1/` deve ser bloqueada.
- [x] Duplicação: Fazer upload do mesmo arquivo duas vezes com o mesmo dono
      retorna o mesmo ID (por `content_hash`).

**Implementado e testado ao vivo no navegador** (2026-07-13): todos os 7 itens
do checklist acima confirmados, incluindo o teste de precisão do TOC — clicar
num capítulo (PDF e EPUB) pula para o índice de token exato via
`engine.seekToIndex()`, verificado batendo o índice esperado calculado à mão
contra o retornado pela API. Ajustes feitos durante a implementação, além do
que estava no plano:
- **Token index calculado por contagem de palavras cumulativa, não por
  conversão de character offset.** O plano original sugeria
  `len(text[:char_offset].split())`, mas nem PyMuPDF (só dá número de página
  no outline) nem o mapeamento de capítulo do EPUB fornecem naturalmente um
  character offset preciso — e um offset caindo no meio de uma palavra
  quebraria a paridade com o tokenizer JS. Em vez disso, o índice de cada
  entrada do TOC é a contagem de palavras acumulada até o início da
  página (PDF) ou do arquivo de capítulo (EPUB) — nunca cai no meio de uma
  palavra, e verificado exato nos dois formatos.
- **Granularidade do TOC em PDF é por página** (a API do PyMuPDF só dá o
  número da página no outline, não uma posição dentro dela) — o salto vai
  para o início da página do capítulo, não para a linha exata do título.
- **Granularidade do TOC em EPUB é por arquivo do spine** — uma entrada de
  TOC apontando pra uma âncora dentro de um arquivo (comum em EPUBs de
  arquivo único) cai no início do arquivo inteiro, não na sub-seção exata.
  Aceito como simplificação (YAGNI) — cobre o caso comum de um
  capítulo por arquivo.
- **Proteção SSRF por resolução de IP, não checagem de string.** Resolve o
  hostname via `socket.getaddrinfo` e verifica se o IP resultante é loopback
  (`ipaddress.ip_address(...).is_loopback`) — cobre `localhost`, `127.0.0.1`
  e variações, não só uma comparação textual. Limitação aceita, documentada
  no código: não revalida o alvo de um redirect HTTP nem protege contra DNS
  rebinding — aceitável para o modelo de ameaça deste projeto (contas de
  confiança na LAN, não atacante externo adversarial).
- **`UrlImportRequest` ganhou um campo `title` opcional** (não estava no
  schema original do plano) — a aba de URL no modal unificado tem um campo
  de título como a aba de arquivo, então o backend precisava aceitar um
  override em vez de usar sempre o título extraído da página.
- **Dependência nova não prevista:** `python-multipart`, exigida pelo
  FastAPI para aceitar `UploadFile`/`Form` — sem ela o servidor nem sobe.

**Correção pós-teste (2026-07-13):** Samuel testou com um livro real (EPUB,
918.917 caracteres) e esbarrou no `MAX_TEXT_CHARS` de 500.000 — limite
criado na Fase 1 pra pegar colagem acidental de texto enorme, baixo demais
pra upload de livro de verdade. Corrigido diferenciando por origem:
`documents.py::MAX_TEXT_CHARS` (500k) continua valendo só pra colar texto;
`import_routes.py` ganhou `MAX_IMPORT_TEXT_CHARS = 5_000_000` pra
upload/URL — o limite de 50MB do arquivo já é a proteção real ali. Testado
com o livro real do Samuel (146.502 palavras, 26 capítulos) — upload
funcionou.

**Problema encontrado no mesmo teste, NÃO corrigido — ver "Questões em
aberto":** modo Fluxo trava ~6-7s nesse mesmo livro (146.502 elementos de
DOM). Aguardando deliberação do Antigravity antes de qualquer correção.

Nenhum código commitado ainda — aguardando teste e autorização do usuário.

#### [x] Fase 7 — Pastas, busca e prateleiras na biblioteca *(implementada 2026-07-13; hardening validado automaticamente 2026-07-14)*
*Depende de: Fase 5 (`reading_progress.status`); faz mais sentido após a
Fase 6 encher a biblioteca. Plano fechado via deliberação autônoma.*

**Resumo executivo:** Transforma a biblioteca em um painel organizável. Adiciona
busca por título e conteúdo (no backend), organização em coleções simples,
e eleva o status de leitura a um filtro de abas (prateleiras de primeira classe).

**Schema e Migração (bloco MIGRATIONS em `database.py`):**
- A tabela `documents` ganha a coluna `collection TEXT NOT NULL DEFAULT ''`.
- Representa a pasta/coleção onde o documento está. Uma string plana é mais do que
  suficiente para o escopo doméstico (sem necessidade de tabela `folders` relacional, 
  mantendo a simplicidade).

**Novos schemas (`schemas.py`):**
- `DocumentSummary` e `DocumentDetail` ganham `collection: str`.
- O antigo `DocumentRename` vira `DocumentUpdate`, aceitando atualizações parciais:
  `title: str | None = None`, `collection: str | None = None`.

**Endpoints (`app/routers/documents.py`):**
- `GET /documents`:
  - Recebe query param opcional `q: str | None = None`.
  - Se `q` for fornecido, a cláusula WHERE ganha `AND (d.title LIKE ? OR d.raw_text LIKE ?)` com os valores `%q%`. A busca por conteúdo DEVE ser no backend pois o frontend não recebe `raw_text` no summary.
- `PATCH /documents/{id}`:
  - Passa a usar o `DocumentUpdate` e o handler pode ser renomeado para `update_document`. Atualiza o `title` (com `_unique_title`) se enviado. Atualiza a `collection` se enviada.

**Frontend HTML/CSS (`index.html` e `style.css`):**
- A biblioteca (`#library-view`) ganha uma barra de ferramentas no topo (`.library-toolbar`):
  - Input de busca `#library-search` (`type="search"`, debounce).
  - Dropdown `<select id="library-collection-filter">` ("Todas as coleções" como default).
  - Navegação de prateleiras (tabs ou radio buttons estéticos): `[Todos] [Quero Ler] [Lendo] [Lido] [Abandonado]`.
- Novo modal `#edit-doc-modal` com campos para Título e Coleção (substitui o antigo `window.prompt` de renomear). O campo de coleção é de texto livre, permitindo criar/atribuir coleções na hora.
- A seção nativa do `<details id="abandoned-section">` (Fase 5) é **removida**. A visualização de abandonados passa a ser exclusivamente via o tab/filtro "Abandonado", unificando o DOM (uma única lista gerida dinamicamente).

**Frontend JS (`app.js`):**
- Novo estado local: `allFetchedDocs = []`, `currentShelf = "all"`, `currentCollection = ""`, `searchQuery = ""`.
- `fetchLibrary()` (novo flow de `loadLibrary`):
  - Dispara `GET /documents?q=...` (debounced se vindo do input de busca).
  - Armazena em `allFetchedDocs`.
  - Extrai coleções únicas (`collection !== ""`) para popular o `#library-collection-filter`.
  - Chama `renderLibrary()`.
- `renderLibrary()`:
  - Filtra `allFetchedDocs` por `currentShelf` (mapeando "all" -> tudo, "quero_ler" -> `progress_status === "quero_ler"`, etc.) e por `currentCollection`.
  - Limpa `#document-list` e anexa os itens via `buildDocListItem()`.
- O botão `rename-btn` vira "Editar" (lápis) e abre o `#edit-doc-modal` preenchido. O submit dispara `PATCH /documents/{id}` e re-chama `fetchLibrary()`.

**Fora do escopo (Limitações aceitas - YAGNI):**
- Tabela relacional de pastas. (Se o último documento de "Ficção" for deletado, "Ficção" some do `<select>`).
- Coleções aninhadas (sub-pastas).
- Full Text Search (FTS5) nativo do SQLite (O `LIKE` cru é rápido o suficiente para o uso previsto e evita setup de extensões/tabelas virtuais complexas).

**Ajustes feitos durante a implementação (2026-07-13):**
- `LIKE` escapado explicitamente (`ESCAPE '\'`, substituindo `%`/`_` literais
  do termo de busca do usuário) — sem isso, buscar por algo como "100%"
  seria interpretado como wildcard e daria falsos positivos.
- `DocumentUpdate.collection` limitado a 100 caracteres
  (`MAX_COLLECTION_CHARS`), mesmo espírito do limite já existente em título.
- O `<select>` de status por item (Fase 5, D1) **não foi removido** — as
  abas de prateleira são um filtro de biblioteca inteira, o select continua
  sendo a troca rápida por item. Os dois coexistem.
- Confirmado que "Todos" mostra abandonados misturados com o resto (não os
  esconde) — só a aba "Abandonado" isola; em qualquer um dos dois lugares,
  clicar num item abandonado ainda abre o modal de confirmação da Fase 5
  (protótipo de clique acidental preservado, não removido pela unificação
  do DOM).
- Adicionado um `<datalist>` de autocomplete de coleção no modal de editar
  (não estava no plano, custo marginal zero já que a lista de coleções
  únicas já existe pro filtro).

**Testado ao vivo (2026-07-13):** busca por título e por conteúdo (uma
mesma palavra batendo nos dois casos, confirmado com "reforma"); editar
título+coleção via modal; filtro por coleção; as 5 abas de prateleira,
com "Todos" mostrando tudo e "Abandonado" isolando; clique num item
abandonado (em qualquer aba) ainda abre o modal de confirmação e não o
leitor direto. Zero erro no console. Dados de teste revertidos após
validar. Nenhum código commitado ainda — aguardando teste e autorização
do usuário.

**Auditoria de hardening (2026-07-14):** revisão posterior confirmou que
`create_document`, `list_documents`, `get_document`, `update_document` e
`delete_document` fecham toda conexão de `get_connection()` em `finally`,
inclusive nos caminhos 403/404 e em exceção SQL. Um banco temporário verificou
`busy_timeout=5000`, `foreign_keys=ON`, escape literal de `%`/`_`/`\`, PATCH
de coleção e cinco conexões rastreadas sem vazamento.

No frontend, `fetchLibrary()` ganhou `AbortController` + request ID monotônico;
uma busca nova invalida a anterior já no primeiro `input`, antes do debounce.
Teste adversarial A-lenta/B-rápida confirmou que B permanece na tela mesmo se
A concluir por último ou durante os 300ms. O filtro de coleção agora zera um
valor que desapareceu dos resultados, e logout/401 limpa requests, filtros e
DOM da biblioteca antes de outro perfil entrar.

`openLibraryDocument(doc)` centraliza a proteção de abandonados consultando o
status atual. Testes dos cinco contextos de prateleira produziram cinco aberturas
do modal e zero abertura direta; os predicados mantêm abandonados somente em
“Todos” e “Abandonado”. Toolbar, tabs e cards receberam acabamento responsivo
Vanilla CSS, alvos touch, foco visível, semântica ARIA e navegação por teclado.
O navegador embutido não estava disponível nesta auditoria; o layout passou por
validação estrutural/estática e mantém como passo final recomendado a inspeção
visual em Chrome/Android antes do commit.

#### [x] Fase 8 — TTS sincronizado (nos dois modos) *(encerrada e aceita pelo usuário em 2026-07-16)*
*Depende de: Fase 3 (substrato/modos) e Fase 6 (conteúdo real). Plano reaberto e revisado após segunda opinião (2026-07-13).*

**Resumo executivo:** Implementa Text-to-Speech (TTS) guiando o RSVP (o motor descarta o WPM interno e atrela `engine.pointer` aos timestamps do áudio). A arquitetura é desenhada em torno de "blocos canônicos" limitados, com validação de qualidade de alinhamento e endpoints assíncronos que evitam travar o SQLite.

**Schema e DB (`database.py` e `schemas.py`):**
- Nova tabela `tts_blocks`: `id`, `document_id`, `start_token`, `end_token`, `voice`, `model_version`, `audio_path`, `timestamps_json`, `alignment_score`. Com constraint `UNIQUE (document_id, start_token, voice, model_version)`.
- Reutilizar `documents.lang` como sugestão; **não** adicionar `langdetect` nem `detected_language`.

**Geração e Integração Backend (`Kokoro-FastAPI`):**
- O bloco gerador não obedece cegamente ao `token` pedido: o backend determina um "Bloco Canônico" (ex: max 250 palavras, quebrando no `sentenceEnd`).
- Novo endpoint `POST /documents/{id}/tts/blocks`:
  - Recebe `{ "token": X, "voice": Y }`. Idempotente (devolve metadados se o bloco canônico já existir).
  - **Transação Curta:** Fechar conexão SQLite antes de chamar a GPU (Kokoro). Usar Lock em memória por chave única para impedir gerações duplicadas simultâneas.
  - Gravar áudio como `.part` e renomear atomicamente.
  - **Score de Alinhamento:** O script de alinhamento fuzzy (offset de não-brancos) deve calcular um `alignment_score` (% de cobertura) e validar a monotonicidade. Salvar no DB.
- Novo endpoint `GET /documents/{document_id}/tts/blocks/{block_id}/audio`: Autenticado, para servir o arquivo real. Não servir via StaticFiles!

**Frontend: Arquitetura TTS Separada (`tts.js` e `app.js`):**
- Não poluir `rsvp.js`. O `rsvp.js` ganha apenas `syncToIndex(idx)` que não toca timers, só desenha. O loop de `requestAnimationFrame` mora no `tts.js`.
- O chunk visual do RSVP é forçado para 1 (`chunkSize=1`) durante o TTS.
- O ping-pong gapless com 2 `<audio>` foi adiado no MVP de 2026-07-13; os testes reais em 4x justificaram reabrir a decisão e o hardening de 2026-07-14 implementou o par ativo/standby.
- O **prefetch** do próximo bloco ocorrerá assim que o áudio atual *começar* a tocar (e não aos 80%, para garantir que o tempo longo da GPU + rede não crie vácuo).
- A sincronização lê `audio.currentTime` e faz busca binária nos `timestamps` locais do bloco. Atualiza a engine apenas se o `idx` mudar, evitando `rerender()` 60x por segundo.
- **Seeks Arbitrários:** Pular na timeline (TOC, scrubber) paralisa o áudio atual e obriga `tts.js` a pedir o bloco do novo token, resetar o `currentTime` local ao timestamp daquele token no novo bloco, e só então dar play.

**Implementação e hardening (2026-07-14):** a barra do leitor recebeu toggle
acessível “Ativar Narrador”, seletor dinâmico de voz, taxa 0.5–4.0x, WPM
efetivo e buffer configurável de 30–120s. WPM e chunk mecânicos ficam ocultos
durante TTS; o motor visual é
forçado a uma palavra e o chunk salvo do modo volta ao desativar. Voz e taxa
persistem localmente sem ampliar o schema de conta. O layout é Vanilla CSS,
mobile-first, com alvo touch, foco visível, spinner de buffering e
`prefers-reduced-motion`.

`app.js` agora coordena os dois relógios: espaço/botão alternam o driver TTS
quando ativo; TOC, scrubber, rewind/forward e clique no Fluxo convergem em
`navigateToToken()` e usam `ttsDriver.seek()`. Heartbeat, sessão, autosave e
Wake Lock reconhecem áudio tocando; `avg_wpm` fica nulo em sessão narrada.
Troca de documento, biblioteca, logout e 401 fazem reset forte do driver.
Carregamento de documento e descoberta de vozes têm request IDs para impedir
publicação tardia após troca de tela/perfil.

O driver ganhou estado explícito de loading, gerações monotônicas,
`AbortController`, cancelamento de metadata, limpeza dos dois áudios/fila e
guarda inclusive contra Promise tardia de `audio.play()`. `reset()` solta
engine/API/doc/callbacks; `stop()` mantém o contexto somente para reativação no
mesmo documento. A fronteira canônica foi corrigida de 260 para 250 e a versão
de cache passou a `kokoro-82m-b250-r2`, impedindo reutilização de blocos antigos
incompatíveis.

**Validação:** `node --check` passou em `app.js`, `rsvp.js` e `tts.js`;
`compileall` passou no backend. Em 100.000 tokens patológicos, a segmentação
produziu 400 blocos com máximo exato de 250. Harness assíncrono confirmou
cancelamento após stop, latest-seek-wins, clamps de taxa, pausa de play tardio
e liberação de referências no reset. Smoke FastAPI em banco temporário cobriu
autenticação de vozes, geração dos blocos `[0,250)`/`[250,500)` e GET do MP3
autenticado, com Kokoro substituído por resposta determinística somente no
processo isolado. Parser HTML confirmou 93 IDs únicos, zero referência JS
ausente e CSS balanceado. Nenhum dado do `data/app.db` real foi criado ou
alterado pelos testes. O navegador embutido não estava disponível; inspeção
visual e áudio com o Kokoro real permanecem como validação do usuário antes do
commit.

**Correção pós-teste real (2026-07-14):** ao ligar o narrador, o backend
retornou `WinError 10061`: a UI estava integrada, mas não existia Kokoro na
porta 8880 e o `docker-compose.yml` ainda continha somente o comentário do
planejamento antigo. Foi adicionado o serviço oficial Kokoro-FastAPI
`v0.6.0-cu128`, adequado à RTX 5060 Ti/Blackwell, limitado a
`127.0.0.1:8880`, com GPU, restart e healthcheck; o app em Compose espera o
serviço saudável e usa `http://tts:8880`. A lista de vozes v0.6 usa objetos
`{id,name}` e agora é normalizada mantendo compatibilidade com listas antigas.

O primeiro teste real revelou ainda que `/dev/captioned_speech` v0.6 assume
NDJSON streaming; a correção inicial enviou `stream:false`. Validação real:
modelo aquecido em CUDA 12.8, 68 vozes, `pf_dora`/`pm_alex`/`pm_santa`, frase
com 47.661 bytes e 8 timestamps. Pelo endpoint completo, em banco temporário:
alinhamento 1.0, 9 timestamps e MP3 autenticado de 49.965 bytes. O Uvicorn foi
reiniciado e voltou com HTTP 200. Falha de conexão agora vira 503 legível em
vez de expor o `WinError` bruto.

**Hardening pós-uso em 4x (2026-07-14):** o usuário confirmou a sincronização,
mas encontrou dois defeitos reais: ao terminar o arquivo do bloco, o navegador
restaurava `playbackRate` para 1x apesar do slider permanecer em 2x; depois, um
bloco português retornou HTTP 500. Os logs provaram que os sete fragmentos de
áudio tinham sido sintetizados e a falha ocorria somente em
`AudioChunk.combine()`, ao executar `list += None` para um fragmento sem
timestamps. Não houve OOM, restart nem falha CUDA.

O cliente agora consome `stream:true` e agrega NDJSON/MP3/timestamps com limites
estritos, ignorando `timestamps:null`; se o endpoint experimental falhar, usa
`/v1/audio/speech` e o frontend deriva timings monotônicos pela duração real.
Texto tem NFC/controle/teto de 4.000 caracteres, voz usa allowlist, respostas
têm limites, timeouts são separados, retries são classificados, há circuit
breaker e `BoundedSemaphore(1)` para a GPU. Compose usa digest cu128 imutável,
`/health`, superfície reduzida e rotação de logs.

No frontend, `_rate` é canônico e alimenta `defaultPlaybackRate` e
`playbackRate` após metadata e antes de todo play. Dois `<audio>` alternam
ativo/standby; uma fila sequencial de até oito blocos mantém 30–120 segundos de
antecedência (60s padrão). A UI exibe simultaneamente taxa e WPM efetivo
calculado pela duração dos últimos três blocos. Harness reproduziu reset para
1x e confirmou 4x após rollover; em 4x/60s, três blocos foram pedidos com
concorrência máxima 1. Kokoro real gerou 2.006.445 bytes/297 timestamps para
texto português longo; endpoint FastAPI real retornou 200 e voz hostil foi
barrada com 422 antes da GPU. O contêiner terminou healthy, sem OOM/restart.

**Encerramento final (2026-07-16):** após uso real, o relógio visual passou a
rejeitar timelines estruturalmente inválidas, cobertura inferior a 85%, séries
longas de timestamps com duração zero ou divergência superior a 8% da duração
do MP3. Nesses casos, reconstrói timings monotônicos ponderados pela palavra e
pelas pausas de sentença, eliminando o congelamento do Foco enquanto o áudio
continua. O seletor agrupa as 68 vozes por idioma e mostra nome, variante
regional, gênero vocal e indicação de modelo anterior, sem alterar os IDs
usados pela API/cache. O usuário confirmou TTS funcional e sincronizado; Fase 8
fica fechada, sem pendências bloqueantes.

#### [x] Fase 9 — Dashboard de estatísticas (eu × casa) *(encerrada em 2026-07-16)*
*Depende de: Fase 5 (sessões acumuladas — quanto antes a 5 entrar, mais
histórico o dashboard terá no lançamento).*
- WPM médio ao longo do tempo, palavras/dia, tempo total, streaks, taxa de
  conclusão; alternância **individual ↔ casa toda**; gráficos por modo
  (Focus vs Flow) e por documento.
- Respeita `collect_stats` (quem desligou não aparece).
- Reverte o non-goal original "no long-term statistics dashboards".

**Implementação encerrada em 2026-07-16:**
- `GET /stats/dashboard` aceita escopo `me|house` e períodos de 7/30/90/365
  dias ou histórico completo. WPM é ponderado por palavras; sessões TTS sem
  WPM não distorcem a média; rewinds negativos e durações inválidas são
  limitados a zero.
- A visão Casa soma somente perfis com `collect_stats=1`. Totais podem
  incorporar atividade privada consentida, mas títulos privados nunca saem
  no ranking de documentos.
- Painel responsivo em Vanilla HTML/CSS/JS com resumo, gráfico diário SVG,
  comparativo Foco/Fluxo, documentos em destaque, seletor de período e
  controle de consentimento. Fetches concorrentes são cancelados por
  `AbortController`.
- Validação: 10 testes `unittest`, harness TTS, `compileall`,
  `node --check` e `git diff --check`.

### MISSÃO RELEASE 1.0 — prioridade absoluta

> **Congelamento funcional:** a partir desta decisão, nenhuma nova feature das
> Fases 10–28 entra antes da release. Correções de regressão, segurança,
> confiabilidade, acessibilidade essencial e documentação continuam permitidas.

A release será conduzida pelos gates abaixo, nesta ordem. Um gate só avança
depois de implementação completa, testes proporcionais ao risco e registro no
diário.

#### [x] R1 — Segurança de transporte e implantação local *(encerrado em 2026-07-18)*
- HTTPS **opcional**, ativado quando certificado e chave forem configurados;
  HTTP continua sendo o modo simples para LAN doméstica confiável.
- Inicialização padrão em 127.0.0.1; exposição em 0.0.0.0 deve ser uma
  escolha explícita para acesso pela rede local.
- Cookies Secure somente sob HTTPS; HttpOnly e SameSite nos dois modos.
- Aviso visível e diagnóstico quando a aplicação estiver em HTTP.
- Documentar mkcert, instalação opcional da CA e regra de firewall restrita ao
  perfil de rede privada. O software não abre portas no roteador.
**Implementado em 2026-07-18:**
- `scripts/run_server.py` centraliza o bind e o TLS: loopback por padrão,
  qualquer host de rede exige `--lan`, proxy headers ficam desligados e o par
  PEM é validado antes da abertura da porta.
- O runner identifica uma instância compatível já ativa e trata ocupação por
  outro serviço ou modo com mensagem acionável antes de iniciar o Uvicorn.
- Certificados padrão em `certs/` ativam HTTPS automaticamente; pares
  customizados e `--no-https` também são suportados no runner nativo e no
  Compose.
- `SessionMiddleware` recebe `https_only` conforme o transporte oficial;
  testes confirmam `Secure`, `HttpOnly` e `SameSite=Lax` em HTTPS.
- Banner acessível alerta todo acesso HTTP. `/system/transport` informa scheme,
  cookie e LAN; headers defensivos básicos acompanham todas as respostas.
- HTTPS real validado com certificado temporário em
  `https://127.0.0.1:8443`; desktop e 390x844 validados sem overflow ou erros
  de console. Documentação inclui mkcert, confiança móvel e firewall privado.

#### [x] R2 — Backup e restauração mínimos *(encerrado em 2026-07-18)*
- Backup versionado de banco, documentos e configuração necessária.
- Scripts PowerShell/Batch de backup e restauração, com validação de caminhos,
  arquivo íntegro e prevenção de sobrescrita acidental.
- Restaurar o backup em uma pasta limpa e executar PRAGMA integrity_check.
- A interface completa de exportação portátil permanece na Fase 14.

**Implementado em 2026-07-18:**
- Pacote ZIP v1 contém snapshot online do banco, secret_key quando existe,
  manifesto, tamanhos e SHA-256; cache TTS e certificados ficam excluídos.
- Verificação rejeita formato incompatível, arquivos extras ou duplicados,
  corrupção, tamanhos divergentes e banco que falhe no integrity check.
- Restauração usa staging validado, recusa destino não vazio por padrão e,
  com --replace, exige um app.db válido e preserva o diretório anterior como
  rollback.
- Backup real restaurado em pasta limpa: integrity check ok, 3 documentos,
  3 usuários e chave de sessão idêntica, sem tocar no banco de produção.

#### [x] R3 — Congelamento e reprodução do ambiente *(encerrado em 2026-07-18)*
- Fixar versões Python e de todas as dependências.
- Fixar a imagem do Kokoro por versão/digest; eliminar dependência de latest.
- Documentar versões mínimas de Python, Docker, Ollama e modelo recomendado.
- Endurecer o inicializador para detectar dependências, iniciar somente o que
  estiver parado e apresentar erros acionáveis.
- Validar instalação limpa em outra pasta ou máquina.

**Implementado em 2026-07-18:**
- Python nativo definido como >=3.13.11 e <3.14; .python-version fixa 3.13.11.
  requirements.lock congela 42 pacotes diretos e transitivos.
- A imagem da aplicação usa Python 3.13.11 slim-bookworm por tag e digest; o
  Kokoro 0.6.0 CUDA 12.8 já permanece fixado por tag e digest.
- O diagnóstico verifica Python, lock, Docker, Compose, Kokoro e Ollama.
  O launcher só inicia Kokoro quando necessário e segue sem TTS se Docker ou
  o serviço estiver indisponível.
- Mínimos documentados: Docker Engine 24, Compose 2.30 e Ollama opcional 0.32.0
  com qwen3:8b recomendado para futuras perguntas.
- Instalação limpa em C:\tmp e build Linux do zero passaram; ambos carregaram
  todas as dependências e as 29 rotas da aplicação.

#### [x] R4 — Migrações e integridade do SQLite *(encerrado em 2026-07-18)*
- Testar banco vazio, banco legado e execução repetida de init_db().
- Fazer backup antes de migrações e documentar restauração como rollback.
- Executar PRAGMA integrity_check; revisar constraints e índices.
- Garantir try/finally e conn.close() em toda conexão aberta.

**Implementado em 2026-07-18:**
- `PRAGMA user_version` versiona o schema; banco mais novo que a aplicação é
  recusado e a execução repetida de `init_db()` é idempotente.
- Toda migração de banco existente exige primeiro um snapshot v1 verificado em
  `backups/migrations/`. Alterações e reparos rodam em transação, seguidos por
  `integrity_check`, `foreign_key_check` e rollback automático em erro.
- A auditoria do banco real encontrou oito referências órfãs invisíveis nas
  consultas: seis progressos e duas sessões ligados a documentos removidos.
  O backup prévio foi preservado e o reparo eliminou somente essas linhas.
- `documents.owner_id` passou a ter FK em schemas que ainda não possuíam a
  coluna e gatilhos equivalentes nos bancos legados; índices de listagem por
  proprietário/data e deduplicação por proprietário/hash foram adicionados.
- Todas as aberturas por `get_connection()` em aplicação e utilitário de reset
  de senha usam timeout de 5 s e fechamento em `finally`, verificado por AST.
- Banco vazio, legado, execução repetida, schema futuro e rollback foram
  cobertos, incluindo rollback transacional forçado; a suíte completa terminou
  com 38 testes verdes.

#### [x] R5 — Degradação segura das dependências locais *(encerrado em 2026-07-18)*
- Biblioteca e leitor permanecem utilizáveis sem Docker, Kokoro, Ollama ou
  internet.
- TTS e futuras integrações mostram estado indisponível sem derrubar a página.
- Timeouts, cancelamentos, limites de concorrência e mensagens recuperáveis.
- Criar diagnóstico consolidado de aplicação, banco, Kokoro, Ollama, HTTPS e
  versão instalada.

**Implementado em 2026-07-18:**
- `app` e `tts` não possuem mais dependência de startup no Compose. O launcher
  solicita o Kokoro em segundo plano, mas abre a aplicação imediatamente; a
  biblioteca, Foco e Fluxo não consultam serviços opcionais para funcionar.
- Descoberta de vozes tem timeout curto, cache negativo de 10 segundos,
  circuit breaker compartilhado e contrato explícito `available/reason/retry_after`.
  A UI preserva WPM/chunk normais, explica a indisponibilidade e oferece nova
  tentativa sem pausar ou corromper o estado do leitor.
- `GET /system/health` verifica somente aplicação/SQLite; o diagnóstico
  autenticado `GET /system/diagnostics` agrega versão, integridade do banco,
  Kokoro, Ollama, transporte HTTP/HTTPS e independência de internet com sondas
  paralelas, limitadas e sem refletir exceções internas.
- A aplicação ganhou healthcheck HTTP/HTTPS no contêiner e o diagnóstico CLI
  cobre também engine Docker, serviço Ollama e versão instalada. Cinco testes
  de degradação elevaram a regressão Python a 56 casos, além do harness TTS.

#### [x] R6 — Hardening de segurança da aplicação *(encerrado em 2026-07-18)*
- Revisar sessão, CSRF, CSP, CORS, hosts permitidos e rotação no login.
- Limitar tentativas de login sem comprometer o uso doméstico.
- Validar tamanho, tipo e nome de uploads; impedir path traversal.
- Blindar importação por URL contra SSRF, redirecionamentos perigosos e
  respostas excessivas.
- Confirmar que logs e respostas nunca vazam senhas, cookies ou stack traces.

**Implementado em 2026-07-18:**
- Sessão opaca server-side em `auth_sessions`, rotacionada no login, revogada no
  logout e armazenada no SQLite somente como SHA-256. CSRF é obrigatório em
  toda mutação; Host, corpos, enums, tamanhos e intervalos têm validação
  central ou por schema.
- Login limita falhas por conta e IP, mantém resposta e custo criptográfico
  indistinguíveis para usuário ausente e eleva PBKDF2 legado de 200 mil para
  600 mil iterações no próximo acesso válido.
- Uploads validam nome, extensão, MIME, assinatura e estrutura EPUB limitada.
  Importação URL valida cada redirect, recusa IP não público e downgrade,
  conecta ao IP auditado para impedir DNS rebinding e limita tempo e bytes.
- CSP, headers defensivos, request ID, erro genérico e log JSON rotativo evitam
  vazamento de traceback/credenciais. Docs automáticas foram desativadas.
- O contêiner passou a rodar não-root, read-only, sem capabilities e preso ao
  loopback por padrão. O mapeamento completo do OWASP Top 10:2025 está em
  `SECURITY.md`.
- A regressão terminou com 51 testes Python, harness TTS e checks JS verdes;
  o contêiner real iniciou como UID 100 e abriu o SQLite v2 íntegro.

#### [ ] R7 — Release gate automatizado e regressão real
- Cobrir autenticação, importações, biblioteca, progresso, prateleiras,
  abandonados, Foco, Fluxo, TTS 4x, skins, dashboard e opt-out.
- Testar troca de documentos, logout e reinício do servidor durante leitura.
- Executar teste prolongado de TTS/sincronização em alta velocidade.
- Um único comando deve rodar testes Python, harnesses JS, verificações
  estáticas e integridade do banco.

#### [ ] R8 — Polimento essencial de produto
- Onboarding curto, estados vazios, carregamentos e erros acionáveis.
- Tela Sistema/Diagnóstico com versão e saúde dos serviços.
- Overlay de atalhos Shift+?, favicon, ícones, título e manifest básicos.
- Auditoria de teclado, foco, contraste das duas skins, zoom 200%, alvos de
  toque, aria-live e prefers-reduced-motion.
- Documentação de instalação, atualização, backup, restauração e solução de
  problemas.

#### [ ] R9 — Release candidate e publicação
- Gerar 1.0.0-rc1, com changelog e procedimento de rollback.
- Usar por alguns dias em pelo menos dois dispositivos; durante o soak entram
  apenas correções de regressão.
- Repetir todos os gates, criar tag v1.0.0 e publicar os artefatos.

**Critério de saída:** HTTPS opcional funcional, backup restaurado de verdade,
ambiente reproduzível, migrações seguras, dependências degradando sem queda,
hardening revisado, suíte de release verde e RC validada em dois dispositivos.

### Backlog de produto pós-release

As Fases 10–28 permanecem planejadas, mas estão congeladas até a conclusão de
R1–R9. A numeração histórica foi preservada para não quebrar referências.
A parte de HTTPS da Fase 11 foi promovida para R1; a PWA offline continua
pós-release. O backup mínimo foi promovido para R2; a exportação portátil
completa continua na Fase 14.

#### [ ] Fase 10 — Teste de velocidade/compreensão embutido
*Depende de: Fase 5 (grava resultado como dado de desempenho).*
- WPM real medido + perguntas simples de compreensão no próprio leitor (o
  SwiftRead só tem isso no site). Reverte o non-goal original.

#### [ ] Fase 11 — PWA offline real
*Depende de: nada; melhor após o grosso das features para cachear a versão
estável.*
- O HTTPS opcional foi promovido para R1 e bloqueia a release. Esta fase fica
  somente com service worker, cache offline e "adicionar à tela inicial"
  completo. Revisar o `Cache-Control: no-store` de desenvolvimento.

#### [ ] Fase 12 — Polish
- Overlay de atalhos (Shift+?), refinamento de tema/contraste, web manifest
  (ícone+nome), mDNS via Avahi (`reader.local`) com fallback de IP estático
  documentado (mDNS no Android é inconsistente — testar nos aparelhos reais).
- [x] **Fundação visual antecipada em 2026-07-16:** identidade editorial de
  biblioteca em CSS puro (papel, madeira, verde e latão), componentes
  responsivos, temas claro/escuro, estados de foco consistentes e perfis
  acessíveis por teclado. Permanecem pendentes overlay de atalhos, manifest e
  descoberta mDNS. A skin alternativa Odysseus (grafite, coral e ciano) esta
  concluida, selecionavel e persistida por perfil sem dependencias externas.
  Os itens restantes mantem a Fase 12 aberta.

#### [ ] Fase 13 — Administração de contas (self-service) — **NÃO PLANEJADA, precisa deliberação**
*Depende de: uso real acumulado das Fases 4-9 (padrões de conta, permissão e
conteúdo por usuário precisam existir de verdade antes de desenhar
administração em cima deles — desenhar isso agora, sobre uma base ainda
rudimentar de contas, arrisca retrabalho).*
- Trocar a própria senha (usuário logado, sem precisar do admin).
- Reset de senha assistido por outro caminho que não seja o admin mexendo
  direto no banco (hoje é o comportamento documentado e aceito da Fase 4 —
  ver "Limitações aceitas"; o script `scripts/reset_password.py` é o
  mecanismo atual, uso administrativo local, fora da API/UI).
- Possivelmente: painel de admin (hoje também fora de escopo), gestão de
  perfis (renomear conta, remover conta e decidir o destino dos documentos
  dela), talvez recuperação sem senha alguma (o vínculo é só o perfil em si,
  já que não há e-mail cadastrado — precisa decidir se isso muda).
- **Ainda não deliberado como fazer** — entra no backlog explicitamente sem
  desenho fechado; delibera quando a base de contas parar de ser tão
  rudimentar (mais gente usando de verdade, primeiros pedidos reais de
  "esqueci minha senha" fora do controle do admin).

#### [ ] Fase 14 — Exportação e Backup Portátil (Soberania de Dados)
- Exportação em um clique de um arquivo `.zip` com os documentos originais ePUB/PDF/TXT do perfil logado e um arquivo JSON estruturado com o progresso de leitura, sessões e configurações.
- Importação correspondente para restauração rápida em qualquer outra instância do Leitura Ligeira.

#### [ ] Fase 15 — Acessibilidade: Leitura Biônica e OpenDyslexic
- Opção de visualização "Leitura Biônica" no modo Fluxo (iniciais das palavras em negrito).
- Integração local da fonte open-source OpenDyslexic nas opções de estilo.

#### [ ] Fase 16 — O Mural da Casa (Recomendações e Notas Compartilhadas)
- Painel comum na biblioteca de recomendações locais entre membros da mesma casa.
- Possibilidade de ver comentários/notas deixadas por outros perfis em documentos marcados como públicos/casa.

#### [ ] Fase 17 — Estimativas Dinâmicas de Tempo Restante
- Biblioteca calcula e exibe estimativa de tempo restante baseando-se no WPM médio real do usuário nas últimas sessões do mesmo livro.

#### [ ] Fase 18 — Timeboxing / Pomodoro Integrado
- Cronômetro no leitor para limitar sessões (15, 20, 25 min) com pausa automática e sinal sonoro nativo.

#### [ ] Fase 19 — Dicionário Offline Local
- Exibição de definições semânticas de palavras com dois cliques, puxando de banco de dados offline local sem requisições externas.

#### [ ] Fase 20 — Perfil Convidado Rápido (Somente Leitura)
- Acesso sem senha de um clique para convidados na rede local Wi-Fi.
- O progresso de leitura é efêmero (salvo no cache/sessionStorage do navegador local).
- **Restrição de Acesso:** Convidados têm privilégios estritos de somente leitura (read-only) — eles podem ver a biblioteca de documentos públicos da casa e ler, mas são impedidos de fazer upload de arquivos/URLs ou de excluir documentos.

#### [ ] Fase 21 — Régua de Leitura Visual (Modo Fluxo)
- Régua de foco visual que destaca o parágrafo/bloco ativo e desfoca ou escurece ligeiramente o texto fora da palavra ativa no Modo Fluxo.

#### [ ] Fase 22 — Modo Sono Extremo (OLED Black + Filtro Vermelho)
- Tema de contraste absoluto (fundo preto absoluto #000) e filtro vermelho de software via overlay CSS para leitura no escuro de cabeceira.

#### [ ] Fase 23 — Modo Zen (Leitura Livre de Distrações)
- Toggle de visualização que oculta toda a interface de controles, barras de progresso e botões, restando apenas o texto e o fundo da tela.

#### [ ] Fase 24 — Prateleiras Dinâmicas por Tempo de Leitura
- Agrupamento automático na biblioteca por duração estimada de leitura (ex: "Tempo de Café" < 10min, "Leitura Média" 10-30min, "Leitura Profunda" > 30min).

#### [ ] Fase 25 — Miras Auxiliares ORP (Guias Oculares RSVP)
- Adição opcional de marcas de mira visual finas alinhadas ao caractere vermelho (ORP) para estabilização do olhar em altas velocidades.

#### [ ] Fase 26 — Coleções Hierárquicas (Subpastas via Separador)
- Suporte a subcoleções usando barras como separador de caminho (ex: `Estudos/História`). A biblioteca renderiza os filtros em árvore com recuo visual e pastas retráteis.

#### [ ] Fase 27 — Agrupamento por Séries e Volumes (Lombadas Inteligentes)
- Metadados de Série e Volume para juntar sequências de livros sob um único card expansível na biblioteca, organizando volumes cronologicamente.

#### [ ] Fase 28 — Tags de Matiz Colorida (Etiquetas de Prioridade)
- Criação e associação de tags de texto com cores customizadas para classificação e filtro matricial rápido na biblioteca.

---

## Limitações aceitas (não resolver a menos que seja pedido)

- **Senha sem regras de composição obrigatórias** — novas senhas exigem 8–256
  caracteres, são hasheadas com PBKDF2 e hashes legados sobem de custo no login.
- **HTTP continua permitido para loopback e LAN doméstica confiável** — R1
  adicionou aviso explícito, HTTPS opcional e cookie Secure quando TLS está ativo.
- **Sem reset de senha por UI** — o login já possui limitação por conta/IP;
  recuperação continua pelo `scripts/reset_password.py` administrativo. O
  self-service fica para a Fase 13, ainda não deliberada.
- **Auto-registro aberto na LAN** — qualquer um na Wi-Fi cria um perfil; é
  confiança doméstica por design, não controle de acesso real.
- PDFs de duas colunas ou com muitas notas de rodapé podem extrair em ordem
  bagunçada; documentos escaneados (sem texto) ficam de fora — sem OCR.
- Sites com paywall, JS pesado ou anti-bot falham na extração de URL, sem
  fallback.
- Sem fila para gerações de TTS concorrentes — sequencial basta em casa.
- Abreviações com ponto ("Dr.", "etc.") disparam micro-pausa de fim de frase
  indevida — heurística de correção é arriscada, fica como está.
- Dedup pega só duplicata exata (mesmo hash); quase-iguais entram separados.
- "Palavras lidas" pode inflar: o RSVP avança sozinho (play + tela ligada) e
  saltos de navegação contam como avanço — sem detecção de atenção real.
- Duas pessoas no **mesmo perfil** ainda misturam posição e estatísticas
  (a versão por usuário resolve entre perfis diferentes, não dentro de um).
- Título colidente ganha sufixo automático em vez de erro.
