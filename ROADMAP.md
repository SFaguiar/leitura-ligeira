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

- **Identidade leve, sem segurança real:** tela "quem está lendo?" (perfil
  tipo seletor, sem senha), `user_id` guardado no cliente e enviado nas
  requisições. É confiança de rede doméstica — qualquer um na LAN pode se
  passar por qualquer perfil. *Limitação aceita; PIN opcional fica no backlog
  se um dia incomodar.* (Proposta LEAN — confirmar na fase de contas.)
- **Configurações por conta, sincronizadas pelo servidor** — seguem a pessoa
  entre celular/PC. O cliente já deve acessar settings por um **módulo único
  de get/set** (hoje localStorage por trás); na fase de contas, só esse módulo
  muda para falar com o servidor. Sem retrabalho espalhado.
- **Biblioteca da casa:** documentos têm `visibility` (`house` | `private`) e
  `owner_id`. Padrão é `house`; privado só aparece para o dono.
- **TTS:** Kokoro-82M via Kokoro-FastAPI como serviço Docker na rede do stack
  local de IA (RTX 5060 Ti 8GB) — sem duplicar infra de GPU. PDF: PyMuPDF ·
  EPUB: `ebooklib` · URL: `trafilatura` (sem headless browser).

### Modelo de dados alvo

```
users:
  id, name, created_at

user_settings:                -- 1:1 com users
  user_id (unique),
  wpm_focus, wpm_flow, chunk_size, font_size,
  orp_enabled, nav_close_on_click, nav_pause_on_open,
  theme, collect_stats,
  updated_at

documents:
  id, title, format, source_type (upload|url|paste),
  raw_text, content_hash, word_count, lang,
  owner_id (FK users, nullable p/ legado), visibility ('house'|'private'),
  created_at

reading_progress:             -- funcional: continuar de onde parou
  user_id, document_id, position, updated_at
  (PK composta user_id+document_id — cada pessoa tem SUA posição)

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
GET/POST   /users                        # listar perfis / criar perfil
GET/PUT    /users/{id}/settings          # configurações da conta
POST       /documents                    # paste (depois upload/URL); aceita visibility
GET        /documents                    # biblioteca (casa + privados do usuário atual)
GET        /documents/{id}
PATCH      /documents/{id}               # renomear
DELETE     /documents/{id}
GET/PUT    /documents/{id}/progress      # posição do usuário atual
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

---

## Questões em aberto (fechar antes das fases que dependem delas)

Para a **Fase 4 (contas)**:
1. Nível de identidade: seletor de perfil sem senha (proposta) é suficiente,
   ou quer PIN opcional por perfil desde o início?
2. Tema (claro/escuro) é por conta ou por aparelho? (Proposta: por conta,
   como todo o resto — mais simples e consistente.)
3. Direitos sobre documentos da casa: qualquer um renomeia/exclui (confiança
   doméstica, comportamento atual) ou só quem subiu? (Privados: só o dono,
   isso é dado.)

Para a **Fase 5 (progresso/sessões)**:
4. Escopo do opt-out de estatísticas — proposta: desligar `collect_stats`
   para de gravar **sessões** (event-log de desempenho), mas a **posição de
   leitura continua salva** (é funcionalidade, não telemetria: sem ela
   "continuar de onde parou" quebra). Confirmar se é isso.
5. O que mais precisa entrar no registro de sessão além de WPM médio,
   palavras avançadas, modo, início/fim? (Ex.: documento terminado sim/não
   para taxa de conclusão?)

Para a **Fase 8 (TTS)**:
6. Como obter timestamps por palavra (forced alignment com Whisper na GPU vs
   saída do Piper vs estimativa proporcional) — avaliar quando chegar.

---

## Backlog imediato (entra na Fase 3)

- **[bug] Botão voltar do Android com o painel aberto** volta para a
  biblioteca em vez de fechar o painel. Correção: o painel ganha entrada
  própria no histórico (`pushState` com flag de painel; `popstate` fecha o
  painel primeiro). No modo Flow formal, "voltar" do leitor → biblioteca,
  como hoje.
- **[ajuste] Controles de leitura acessíveis no Flow/painel:** WPM, tamanho
  da fonte e palavras-por-vez hoje só existem na tela do RSVP. O painel
  precisa expô-los (seção compacta/recolhível junto ao transporte).
- Ambos são parte do escopo da Fase 3 (abaixo) — não são itens soltos.

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

#### [ ] Fase 3 — Leitura completa: modos Focus/Flow formais
*Depende de: nada (só frontend). Desbloqueia: TTS (substrato pronto), sessões
com campo `mode`.*
- Seletor Focus/Flow explícito no leitor; modo ativo persistido.
- Trocar de modo preserva ponteiro e estado de play (mesmo motor).
- **WPM separado por modo** (`wpmFocus` / `wpmFlow`); slider mode-aware
  (mostra e grava o valor do modo ativo).
- **Flow destaca o chunk inteiro** (N palavras acesas, marca pula de N em N).
- **Controles no Flow:** WPM, fonte e palavras-por-vez acessíveis do próprio
  painel (backlog acima).
- **Fix do botão voltar** com painel aberto (backlog acima).
- Settings passam a ser acessados por **módulo único** (preparação para a
  Fase 4 trocar o storage por servidor sem retrabalho).
- ORP segue exclusivo do Focus.
- Fonte do Flow independente da fonte do flash RSVP (tamanhos diferentes por
  natureza — corpo de texto vs palavra gigante).

#### [ ] Fase 4 — Contas da casa (multiusuário leve)
*Depende de: Fase 3 (módulo de settings). Desbloqueia: Fases 5, 6 (privado),
9 (stats individuais).*
- Tabela `users` + tela "quem está lendo?" (criar/escolher perfil; sem senha
  — ver questão aberta nº 1).
- `user_settings` no servidor; o módulo de settings do cliente passa a
  sincronizar com a conta; settings atuais do localStorage migram para o
  primeiro perfil criado.
- `documents.owner_id` + `visibility` (`house` default | `private`); o modal
  de paste ganha a opção "privado". Biblioteca lista casa + privados do
  usuário ativo.
- Direitos: privado só o dono vê/gerencia; casa conforme questão aberta nº 3.
- Sem segurança real (LAN doméstica) — documentado como limitação aceita.

#### [ ] Fase 5 — Progresso e sessões por usuário
*Depende de: Fase 4 (user_id). Desbloqueia: Fase 9 (dashboard), gamificação.*
- `reading_progress` por usuário×documento — **cada pessoa continua de onde
  ELA parou** (o pivô dissolveu a antiga limitação de posição única por
  documento).
- `reading_sessions` com `user_id` e `mode`; começa no primeiro play, fecha
  em fim/saída/5 min de inatividade; heartbeat ~30s + envio explícito ao
  pausar/sair/minimizar.
- **Opt-in/out de coleta por usuário** (`collect_stats`) — escopo conforme
  questão aberta nº 4.
- Limitações mantidas: "palavras lidas" pode inflar (play sozinho, saltos de
  navegação contam) — sem detecção de atenção.

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

#### [ ] Fase 7 — Pastas + busca na biblioteca
*Depende de: nada tecnicamente; faz mais sentido após a Fase 6 encher a
biblioteca.*
- Pastas/coleções e busca por título/conteúdo (lacunas do SwiftRead
  original). Respeita visibilidade (privados só na visão do dono).

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
  = questão aberta nº 6). **Flow:** karaoke no texto (marca segue a fala).
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

---

## Limitações aceitas (não resolver a menos que seja pedido)

- **Sem segurança real entre perfis** — qualquer um na LAN escolhe qualquer
  perfil; é confiança doméstica por design (PIN opcional só se incomodar).
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
