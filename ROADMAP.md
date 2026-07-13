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
- **Deploy:** Docker Compose; LAN apenas; HTTP puro (HTTPS na fase de PWA).
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
  (estilo Netflix).** **Tensão aceita:** a senha trafega em HTTP puro até a
  Fase 11 (HTTPS) — ok numa LAN de confiança doméstica; revisitar se a rede
  deixar de ser só isso.
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
- **Decisões do usuário:** HTTP puro aceito por ora (HTTPS fica na Fase 11);
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

## Questões em aberto (fechar antes das fases que dependem delas)

Para a **Fase 8 (TTS)**:
1. Como obter timestamps por palavra (forced alignment com Whisper na GPU vs
   saída do Piper vs estimativa proporcional) — avaliar quando chegar.

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
rate-limiting/lockout de login. Senha em HTTP puro até a Fase 11.

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

#### [ ] Fase 6 — Import: arquivo + URL (+ TOC)
*Depende de: Fase 4 (visibilidade/owner no upload). Desbloqueia: TTS com
conteúdo real, Fase 7 (biblioteca cheia pede organização).*
- Upload PDF (PyMuPDF) / EPUB (`ebooklib`) / TXT; paste de URL via
  `trafilatura` (sem headless browser; paywall/JS pesado falham com erro
  claro).
- Opção "privado" no upload. `format`/`source_type` refletem o tipo real.
- **TOC como camada sobre o painel/Flow:** capítulos do EPUB e outline do PDF
  mapeados a índices de token; texto colado continua sem TOC.
- Limitações aceitas: PDF de 2 colunas/notas → ordem bagunçada; escaneado
  (sem texto) fora — sem OCR.

#### [ ] Fase 7 — Pastas, busca e prateleiras na biblioteca
*Depende de: Fase 5 (`reading_progress.status`); faz mais sentido após a
Fase 6 encher a biblioteca.*
- Pastas/coleções e busca por título/conteúdo (lacunas do SwiftRead
  original). Respeita visibilidade (privados só na visão do dono).
- **Filtro/agrupamento por prateleira** (quero ler/lendo/lido/abandonado) —
  as prateleiras da Fase 5 viram navegação de verdade na biblioteca, não só
  um campo salvo sem uso.

#### [ ] Fase 8 — TTS sincronizado (nos dois modos)
*Depende de: Fase 3 (substrato/modos), idealmente Fase 6 (conteúdo real).
Consolida geração + sincronização numa fase só — "fechar toda a questão do
TTS de uma vez".*
- **Geração:** Kokoro-82M via Kokoro-FastAPI (Docker, rede do stack de IA,
  RTX 5060 Ti). Cache por `(document_id, voice)` — biblioteca compartilhada
  gera uma vez, todos reaproveitam. Auto-detecção de idioma (`langdetect`)
  para voz padrão PT-BR/EN; troca manual por documento. Sem fila (sequencial,
  escala doméstica). Tabela `generated_audio`.
- **Sincronização por palavra:** timestamps cacheados junto do áudio (método
  = questão aberta nº 1, acima). **Flow:** karaoke no texto (marca segue a fala).
  **Focus:** flash guiado pelo relógio do áudio (não pelo timer de WPM — a
  prosódia não casa com ritmo fixo).
- O relógio do highlight já é plugável desde a Fase 3 — aqui só troca a
  fonte de tempo.
- Stretch posterior (fase própria se necessário): Chatterbox-Turbo (MIT)
  como segunda engine para inglês mais natural — só depois do Kokoro rodar
  de ponta a ponta.

#### [ ] Fase 9 — Dashboard de estatísticas (eu × casa)
*Depende de: Fase 5 (sessões acumuladas — quanto antes a 5 entrar, mais
histórico o dashboard terá no lançamento).*
- WPM médio ao longo do tempo, palavras/dia, tempo total, streaks, taxa de
  conclusão; alternância **individual ↔ casa toda**; gráficos por modo
  (Focus vs Flow) e por documento.
- Respeita `collect_stats` (quem desligou não aparece).
- Reverte o non-goal original "no long-term statistics dashboards".

#### [ ] Fase 10 — Teste de velocidade/compreensão embutido
*Depende de: Fase 5 (grava resultado como dado de desempenho).*
- WPM real medido + perguntas simples de compreensão no próprio leitor (o
  SwiftRead só tem isso no site). Reverte o non-goal original.

#### [ ] Fase 11 — HTTPS local + PWA offline real
*Depende de: nada; melhor após o grosso das features para cachear a versão
estável.*
- mkcert para contexto seguro; service worker (cache de assets, offline,
  "adicionar à tela inicial" completo). Revisar o `Cache-Control: no-store`
  de desenvolvimento. Reverte o "só HTTP puro" original.

#### [ ] Fase 12 — Polish
- Overlay de atalhos (Shift+?), refinamento de tema/contraste, web manifest
  (ícone+nome), mDNS via Avahi (`reader.local`) com fallback de IP estático
  documentado (mDNS no Android é inconsistente — testar nos aparelhos reais).

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

---

## Limitações aceitas (não resolver a menos que seja pedido)

- **Senha sem exigência de complexidade obrigatória** — ambiente doméstico,
  cada um escolhe a própria senha. Ainda é hasheada (pbkdf2) e verificada de
  verdade (não é "sem segurança real").
- **Senha trafega em HTTP puro até a Fase 11** (HTTPS local) — aceitável numa
  LAN de confiança doméstica; revisitar (ou adiantar a Fase 11) se a rede
  deixar de ser só isso.
- **Sem rate-limiting/lockout no login e sem reset de senha por UI** — home,
  confiança, baixo risco. Esqueceu a senha? O admin roda
  `scripts/reset_password.py` (CLI oculto, fora da API/UI, acesso direto ao
  banco). Self-service fica pra Fase 13, ainda não deliberada.
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
