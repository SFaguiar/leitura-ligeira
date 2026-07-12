# Roadmap — Leitura Ligeira

Leitor RSVP self-hosted, single-user, sem login, para uso doméstico via Wi-Fi.
Clientes principais: celulares na rede Wi-Fi de casa, acessando como web app
comum (sem extensão de navegador, sem app nativo).

## Arquitetura

- **Backend:** Python + FastAPI
- **Banco:** SQLite, arquivo único, schema mínimo, sem tabela de usuários
- **Frontend:** JS puro (vanilla) + HTML/CSS, sem build step nem framework —
  o loop de timing do RSVP e o estado do player não precisam da complexidade
  de React/Vue, e um pipeline de build é custo de manutenção sem retorno
  nessa escala
- **PDF:** PyMuPDF (`fitz`) · **EPUB:** `ebooklib` · **URL:** `trafilatura`
  (sem headless browser/Playwright/Puppeteer)
- **TTS:** Kokoro-82M (Apache 2.0) via Kokoro-FastAPI (API compatível com
  OpenAI), como serviço Docker separado, na mesma rede Docker do stack local
  de IA já existente (RTX 5060 Ti 8GB) — evita duplicar infra de GPU
- **Deploy:** Docker Compose, um serviço para o app + um para o TTS, acesso
  só via LAN (sem VPN/remoto), sem HTTPS/TLS na v1 original (revertido na
  Fase 9, ver abaixo)

### Modelo de dados (rascunho, ajustar durante a implementação)

```
documents:
  id, title, format, source_type (upload | url | paste),
  raw_text, content_hash, created_at

generated_audio:
  document_id, voice, file_path, created_at
```

### Superfície de API (rascunho, ajustar durante a implementação)

```
POST   /documents                      # upload de arquivo, ou paste de texto/URL no corpo
GET    /documents                      # lista a biblioteca
GET    /documents/{id}                 # texto + metadados
PATCH  /documents/{id}                 # renomear (título único, sufixo automático em colisão)
DELETE /documents/{id}                 # excluir
POST   /documents/{id}/audio?voice=...  # gera ou retorna narração já cacheada
GET    /documents/{id}/audio/{voice}   # stream do áudio cacheado
```

## Decisões que revertem os non-goals originais

- **Estatísticas de longo prazo** (Fase 7) e **teste de velocidade/compreensão**
  (Fase 8): o spec original excluía isso explicitamente ("no long-term
  statistics dashboards", "no comprehension quizzes"); decidimos incluir
  como fases futuras, depois do núcleo pronto e estável.
- **PWA offline real** (Fase 9): o spec original mandava servir HTTP puro e
  aceitar que isso impede o service worker (contexto seguro é exigido).
  Decidimos configurar HTTPS local via mkcert só para habilitar isso de
  verdade.
- **Sync palavra-a-palavra TTS/RSVP** (Fase 10): o spec original tratava
  isso como decisão arquitetural deliberada ("not an oversight") — TTS e
  RSVP deveriam ficar como modos independentes, sem alinhamento por
  palavra, sem Whisper. Revertemos essa decisão. Em aberto: como extrair os
  timestamps por palavra do Piper (saída nativa do modelo vs. um passo de
  alinhamento forçado à parte, tipo Whisper/aeneas) — não é trivial em
  todos os wrappers e precisa ser avaliado quando chegarmos lá.

## Decisões registradas (antes estavam implícitas no código)

Levantadas na revisão profunda das Fases 1 e 1.5 (2026-07-11). Registradas
aqui para não se perderem; as marcadas "a implementar" viram trabalho na
Fase 1.6.

- **WPM é efetivo, não nominal** *(implementado em 2026-07-12)*. O delay por
  chunk agora é `(60000/wpm) × (peso_do_chunk / peso_médio_do_documento)`, com
  `peso_médio` calculado uma vez em `load()`. A soma dos delays do documento
  inteiro = `N × 60000/wpm` exatamente — o WPM do slider passou a ser
  throughput real, não mais uma taxa nominal ~15–25% otimista. **Nota
  registrada no README:** isso recalibra a percepção — quem já tinha calibrado
  uma velocidade confortável antes precisa recalibrar.
- **rewind/forward pausam a reprodução e navegam por frase, não por
  palavra/chunk** *(revisado em 2026-07-12)*. A unidade lógica de navegação
  manual é a frase — mais importante cognitivamente do que precisão de
  palavra. `forward()` pula para o início da próxima frase.  `rewind()`
  segue a semântica clássica de "voltar" de player de música: se o ponteiro
  está no meio de uma frase, volta para o início dela; se já está exatamente
  no início, volta para o início da frase *anterior*. Sempre pausa a
  reprodução (retomar é explícito via play). Implementado com
  `_sentenceStart`/`_sentenceEndIndex` em `rsvp.js`, reaproveitando o flag
  `sentenceEnd` já existente no tokenizer.
- **Chunk não cruza parágrafo nem frase** *(implementado em 2026-07-12)*.
  `_currentChunk` agora monta o chunk token a token e para assim que inclui um
  token com `paragraphEnd` ou `sentenceEnd` — mesmo que isso resulte num chunk
  menor que o "palavras por vez" configurado. Efeito colateral esperado e
  aceito: perto de fins de frase/parágrafo, o chunk visual pode variar de
  tamanho (1–N palavras) em vez de ser sempre fixo.
- **Pesos das micro-pausas são constantes hardcoded** (vírgula +0.35; fim de
  frase +0.9; palavra longa/número +0.5; parágrafo +1.2). Não configuráveis por
  UI na v1 — eventual "intensidade de pausa" fica para um settings futuro.
- **Dedup é hash exato** (SHA-256) do texto aparado. Quase-duplicatas (espaços
  ou caixa diferentes) contam como documentos distintos — comportamento aceito.
- **Unicidade de título** é imposta com sufixo numérico (`(2)`, `(3)`…),
  inclusive no rename.
- **`created_at` é UTC**; o cliente converte para o fuso local na exibição.
- **`Cache-Control: no-store`** em todas as respostas é intencional nesta fase de
  desenvolvimento (evita servir build velho). Revisar na Fase 9, quando o PWA
  precisar de cache real de assets.

## Fase 1.6 — Hardening da fundação (P0 + P1 implementados, 2026-07-12)

Fruto da revisão profunda das Fases 1 e 1.5. Objetivo: fechar as lacunas de
base **antes** da Fase 2, porque é a parte onde o usuário passa mais tempo e o
custo de mudar depois é maior. P0 e P1 implementados e testados ao vivo no
navegador; P2 é só documentação de limitações conhecidas, não implementação
(ver abaixo) — não há mais trabalho de código pendente nesta fase.

### [x] P0 — fundação (correção clara, alto impacto no feel)
- [x] Persistir WPM/chunk/fonte no localStorage e reaplicar no load (hoje só o
      tema persiste; tudo volta a 300/1/48px toda sessão)
- [x] Wake Lock durante a reprodução (a tela do celular apaga no meio da
      leitura hands-free — quebra o caso de uso central; API confirmada
      disponível)
- [x] Tap-to-play/pause na área da palavra (gesto primário no celular; spec §4
      previa "tap na tela")
- [x] Histórico real de navegação: `pushState` + `popstate` + ler hash no load,
      para o botão/gesto "voltar" do Android ir do leitor → biblioteca em vez de
      sair do site; e recarregar dentro do leitor não cair na biblioteca
- [x] Chunk não cruza parágrafo/frase (ver decisão acima)
- [x] Estado de fim claro: mostrar "Fim" e completar a barra em 100% (hoje a
      última palavra congela e a barra para pouco antes do fim)
- [x] `preventDefault` nas setas (senão a página rola junto) + corrigir possível
      duplo-toggle do Espaço quando um botão está focado (blur no botão após
      clique)
- [x] **(bônus, fora do P0 mas decidido junto)** WPM normalizado para efetivo —
      ver "Decisões registradas" acima; `RSVPEngine` agora calcula o peso médio
      do documento em `load()` e normaliza o delay por chunk

### [x] P1 — robustez (implementado, 2026-07-12)
- [x] `PRAGMA journal_mode=WAL` (ativado uma vez em `init_db`, persiste no
      arquivo do banco) + `busy_timeout=5000` (por conexão, em `get_connection`)
- [x] Data em ISO com `T`/`Z` gerada explicitamente em Python (`_iso_now()`),
      não mais via `DEFAULT` do SQL — `CREATE TABLE IF NOT EXISTS` não altera o
      default de uma coluna já existente, então depender só do schema não
      bastava para bancos já criados. Timestamps antigos (espaço em vez de
      `T`) migrados automaticamente em `init_db`.
- [x] Coluna `word_count`; biblioteca mostra "N palavras · ~M min" (estimativa
      usa o WPM persistido do próprio usuário). Documentos antigos tiveram o
      `word_count` recalculado a partir do `raw_text` na migração.
- [x] Shrink-to-fit em `fitDisplayText()` (app.js) — reduz a fonte até caber
      numa linha só, com piso de ~35% do tamanho base. **Bug encontrado e
      corrigido durante o teste:** `showReader()` chamava `engine.load()`
      antes de tornar a view do leitor visível, então a primeira palavra de
      cada documento era medida com `rsvp-stage` em largura zero (elemento
      oculto) e encolhia pro mínimo por engano, mesmo sendo uma palavra curta.
      Corrigido invertendo a ordem: view visível primeiro, load depois.
- [x] Limite de 500.000 caracteres em `raw_text` (413 com mensagem amigável) e
      200 caracteres em `title` (truncado silenciosamente, sem erro)
- [x] Modal: Esc fecha, clique no backdrop fecha (clique dentro do card não
      fecha), Enter no campo de título salva (Enter no textarea continua
      inserindo quebra de linha, não submete)
- [x] Coluna `lang` adicionada (nullable, populada só na Fase 3) e
      `PRAGMA foreign_keys=ON` habilitado por conexão — as tabelas de
      áudio/progresso ainda não existem (Fases 3/5), então o `ON DELETE
      CASCADE` em si fica para quando forem criadas; o que dava pra fazer
      agora (garantir que FKs futuras realmente cascateiem) já está pronto.

### P2 — revisado com o usuário em 2026-07-12
- [x] **Abreviações geram falsa pausa de fim de frase** — confirmado manter
      como limitação conhecida (já documentada em "Limitações aceitas"), sem
      código
- [x] **Micro-pausas configuráveis por UI** — confirmado manter adiado
      ("settings futuro"); pesos continuam constantes hardcoded no tokenizer
- [x] **ORP com pivô fixo** — usuário decidiu reverter o non-goal do spec e
      implementar agora. Toggle "Destaque ORP" na UI (persistido em
      `localStorage`), `computeOrpIndex(word)` em `rsvp.js` (heurística
      clássica estilo Spritz: pivô em 0/1/2/3/4 conforme o comprimento da
      palavra cresce). Com chunk size 1, layout flex com pivô ancorado na
      posição horizontal fixa da tela (`before`/`pivot`/`after` como
      flex-grow simétrico); com chunk size >1, cada palavra recebe seu
      próprio pivô colorido inline, sem o alinhamento fixo (que só faz
      sentido pra uma palavra por vez). Renderização trocou de `textContent`
      para `innerHTML` — adicionado `escapeHtml()` e testado contra XSS
      (texto colado com `<script>`, `&`, aspas) antes de considerar pronto.
- [x] **Bug do ORP corrigido (2026-07-12):** ativar o ORP encolhia a fonte ao
      mínimo. Causa: o layout ORP de palavra única estica o display pra
      `width:100%` (pra ancorar o pivô), então o `fitDisplayText()` media o
      container esticado e achava que sempre transbordava. Corrigido medindo a
      largura intrínseca do texto numa sonda off-screen (`measureProbe`), em
      vez do elemento com layout flex.

## Feedback de uso real — deliberado e priorizado (2026-07-12)

Uso real do usuário: colou um capítulo inteiro de EPUB (convertido pra TXT)
pra testar a experiência com um texto longo de verdade. As decisões abaixo
foram tomadas e **reorganizaram a fila de fases** (ver "## Fases"). A
diretriz-mãe: o módulo de leitura tem que estar praticamente completo em
funcionalidade **antes** de partir pro TTS — e o TTS será uma fase única e já
sincronizada ("fechar toda a questão do TTS de uma vez").

**O problema relatado:**
- Navegar num texto grande foi "simplesmente impraticável" usando só
  rewind/forward — mesmo com a navegação por frase (já implementada na Fase
  1.6) isso não basta na escala de um capítulo inteiro: muitas frases entre o
  ponto atual e onde o usuário quer chegar.
- Falta noção de quanto falta pra terminar *durante* a leitura — a
  biblioteca já mostra tempo estimado do documento inteiro (Fase 1.6 P1), mas
  isso é antes de começar a ler, não uma contagem regressiva viva.
- Falta uma forma de navegar *para um trecho específico* do texto importado,
  não só sequencialmente.

**Ideias levantadas pelo usuário:**
- Um painel que aparece/some com o texto original completo; clicar num
  trecho leva exatamente pra aquele ponto no leitor RSVP.
- Uma barra/indicador de progresso mais detalhado do que a barra fina atual.
- Guardar os dados de progresso de leitura de um jeito que sirva no futuro
  pra gamificação ou um dashboard — não só "continuar de onde parou".

**Conexão com o que já está planejado:**
- A "navegação para trecho específico" é essencialmente o que o spec
  original (seção 4, antes de eu cortar escopo pro clone self-hosted) chamava
  de **Table of Contents** e **Reader vs. Source view** — features que
  existiam na análise do SwiftRead original mas nunca entraram no spec de
  build enxuto que viramos a usar. Foi uma lacuna real de escopo, não uma
  omissão deliberada.
- "Guardar progresso pensando em gamificação/dashboard futuro" amplia
  bastante o que a Fase 5 (hoje só "salvar posição, continuar de onde
  parou") e a Fase 7 (estatísticas) precisam cobrir — pode exigir desenhar o
  schema de progresso já pensando nisso, e não só um `position INTEGER`.

**Decisões tomadas (respostas do usuário em 2026-07-12):**
1. **Clique por palavra.** O painel mostra o texto completo rolável e cada
   palavra é um alvo de clique — pula exatamente pra ela. Sai de graça do
   array de tokens; a palavra atual fica destacada durante a leitura.
2. **Painel e TOC são separados; o painel é a base.** O painel de navegação
   (palavra/parágrafo) funciona pra qualquer texto já agora. O TOC (lista de
   capítulos) é uma camada extra que só "acende" quando o import (Fase 4)
   trouxer EPUB/PDF com estrutura real de capítulos.
3. **Progresso detalhado = (C): as duas coisas.** Contagem viva de
   palavras/tempo restante *durante* a leitura **e** barra mais granular
   (que também vira scrubber arrastável, reaproveitando o `seekFraction()`
   que o engine já tem).
4. **Sim, a fila mudou.** Navegação e progresso furam a fila e vêm antes do
   import (detalhes na seção "## Fases"), porque a dor é sobre a experiência
   *central* de leitura, não sobre ter mais formatos de entrada.
5. **Estatísticas compartilhadas (casa como um usuário), schema pensando em
   gamificação.** Sem tabela de perfis / sem seletor de "quem está lendo" —
   coerente com a biblioteca única sem login. Mas o schema de progresso já
   nasce com uma tabela de *sessões de leitura* (não só um `position INTEGER`)
   pra guardar WPM médio ao longo do tempo, palavras lidas por dia e o que
   mais for preciso pra reforço de hábito/dashboard futuros.

**Sacada arquitetural que orienta a ordem:** o painel de texto clicável com
"palavra atual destacada" é o **mesmo substrato** que o TTS sincronizado
(karaoke) vai precisar. Construir a navegação primeiro (renderizar o texto com
um `<span>` por token, marcar/rolar até o token atual) de-risca o TTS depois —
por isso a navegação vem cedo e o TTS consolidado vem logo após o módulo de
leitura estar completo.

**Limitação nova aceita:** o RSVP avança sozinho, então "palavras lidas" pode
inflar se o usuário der play e sair de perto (o Wake Lock mantém a tela
ligada). É análogo à limitação das abreviações — difícil resolver sem detectar
atenção. Mitigação possível na Fase 3 (nova): só contabilizar palavras quando
houve interação recente. Documentado abaixo.

## Deliberação de detalhamento — Fase 2 e 3 (2026-07-12, segunda rodada)

Antes de codar a Fase 2, resolvemos as lacunas concretas de UX/schema que
faltavam. Registro aqui as decisões e o raciocínio, para não se perderem.

**Painel de navegação — formato:** overlay/drawer que cobre a tela (não
split-view lateral) — decisão do agente, sem objeção; uma implementação só,
funciona igual em celular e desktop. Split-view lateral fica pra nunca, a
menos que sinta falta no desktop depois.

**Painel — fechar ao clicar numa palavra:** **configurável por usuário**,
com **"continuar aberto" como padrão**. Clicar pula a posição do RSVP e
atualiza o destaque no painel, mas não fecha sozinho — o usuário fecha quando
quiser (útil pra explorar/comparar trechos antes de decidir onde parar). Um
toggle nas configurações do leitor (mesmo padrão visual do toggle de ORP)
liga o fechamento automático pra quem preferir esse fluxo.

**Painel — pausar automaticamente ao abrir:** **configurável por usuário**,
com **"pode ficar aberto durante o play" como padrão**. Outro toggle nas
configurações liga a pausa automática pra quem preferir o modo mais simples
(painel = foto estática, sem brigar com scroll).

> **Consequência importante desta escolha:** como o padrão permite o painel
> aberto durante a reprodução, o **modo "seguir"** (auto-scroll rolando o
> painel pra acompanhar a palavra atual enquanto o RSVP toca) precisa ser
> implementado de verdade — não dá pra evitar simplificando o design, como eu
> tinha cogitado antes. Regra: auto-scroll ativo por padrão quando o painel
> abre; qualquer scroll manual do usuário desliga o auto-scroll (mostra um
> botão flutuante "voltar pra posição atual" que religa o modo seguir ao ser
> tocado). Vale para os dois casos (pausado ou tocando) — a diferença é que,
> com "pausar ao abrir" desligado, o destaque se move sozinho pela tela
> enquanto o RSVP avança.

**Granularidade de clique:** por palavra (já decidido na rodada anterior).
Parágrafos continuam visualmente separados (espaçamento) no painel, mesmo
com o alvo de clique sendo a palavra individual.

**Performance do painel:** construir o DOM completo (um `<span>` por token)
só na primeira vez que o painel abre por documento, cachear o resultado
(reabrir não reconstrói), um único listener de clique no container via
event delegation. Sem virtualização por enquanto — o limite de 500k
caracteres (~80k palavras) é caso extremo; a maioria dos textos reais
(um capítulo) é bem menor. Revisitar só se a prática mostrar lentidão real.

**Contador vivo de palavras/tempo restante:** linha pequena e discreta,
sempre visível (não escondida atrás de pausa/painel), acima ou abaixo da
barra de progresso, recalculada a cada chunk. `tempo restante = palavras
restantes ÷ WPM efetivo` — preciso de verdade graças à normalização de WPM
da Fase 1.6.

**Scrubber (arrastar a barra de progresso):**
- Arrastar pausa a reprodução, por consistência com rewind/forward/clique no
  painel (regra geral: qualquer mudança manual de posição pausa).
- **Marcadores de parágrafo: mostrar todos, estilo sutil** (traço fino, baixa
  opacidade) — decisão confirmada após mockup visual. Sem lógica de corte
  por densidade; a sutileza do CSS já resolve textos com muitos parágrafos.

**Sessão de leitura (Fase 3) — parâmetros fechados:**
- Começa no primeiro play (não simplesmente ao abrir o documento).
- Termina em: fim do documento, saída do leitor, ou **5 minutos de
  inatividade** (confirmado).
- Detecção robusta sem app nativo: **heartbeat** a cada ~30s enquanto está
  tocando, atualizando `ended_at` e palavras avançadas no servidor — limita a
  perda de dado por fechamento abrupto da aba a ~30s, aceitável pra uma
  feature de hábito pessoal (não precisa ser cirúrgico). Complementado por um
  envio explícito ao pausar/sair/minimizar quando o navegador permitir.
- Schema (rascunho):
  ```
  reading_sessions:
    id, document_id, started_at, ended_at,
    start_pointer, end_pointer, words_advanced, avg_wpm

  reading_progress:                          -- separado, "continuar de onde parou"
    document_id (unique), position, updated_at
  ```
  `avg_wpm` = média da configuração do slider amostrada nos heartbeats (não o
  throughput real incluindo pausas — isso é derivável depois de
  `words_advanced` e a duração, sem precisar guardar de novo — schema
  mínimo).
- "Palavras avançadas" aceita saltos grandes (clique no painel, arrastar o
  scrubber) como parte da contagem, sem tentar diferenciar "pulei" de "li"
  — mesma filosofia das outras limitações já aceitas (abreviações, dedup).

## Fases

### [x] Fase 1 — Núcleo: RSVP engine + player + paste-text
- RSVP modo Focus: um chunk por vez, centrado, posição fixa
- WPM: 100–1000, passo 10, ao vivo (slider)
- Chunk size ("words at a time"): 1–4 palavras por flash, ao vivo
- Micro-pausas (o detalhe mais importante da sensação de leitura): multiplicador
  extra de delay em vírgulas/pontos finais/fim de frase, em palavras
  longas/números, e em quebras de parágrafo
- Controles do player: play/pause, rewind/forward por um chunk
- Tema claro/escuro, controle de tamanho de fonte
- Import: só paste de texto direto (sem upload, sem URL, sem TTS ainda) —
  o objetivo é validar a sensação de leitura antes de qualquer outra coisa
- **Feito:** engine + player + import por paste, dedupe por hash de conteúdo,
  título único automático em colisão

### [x] Fase 1.5 — CRUD básico da biblioteca (adicionada fora de ordem)
- Não estava atribuída a nenhuma fase originalmente — só aparecia implícita
  na lista de limitações aceitas ("alguém apaga um documento que outra
  pessoa está lendo"), o que pressupõe que excluir existe, mas nunca virou
  item de fase. Coleções/pastas continuam na Fase 6; isto aqui é só o CRUD
  mínimo.
- Excluir documento (`DELETE /documents/{id}`), com confirmação na UI
- Renomear documento (`PATCH /documents/{id}`), reaproveitando a lógica de
  título único já usada na criação
- **Feito:** endpoints + botões de renomear/excluir na lista da biblioteca

> **Fila reorganizada em 2026-07-12** (ver seção "Feedback de uso real"). A
> ordem antiga era: import → TTS → polish → progresso → pastas → stats. A
> nova ordem completa o *módulo de leitura* (navegação + progresso) antes de
> adicionar fontes de conteúdo, e consolida todo o TTS numa fase única já
> sincronizada. Numeração renumerada; mapeamento pra numeração antiga
> anotado em cada fase.

### BLOCO A — Completar a experiência de leitura (antes do TTS)

### [ ] Fase 2 — Navegação no texto *(nova; nasce do feedback de uso real)*
O objetivo é matar a dor de "navegar um capítulo inteiro é impraticável só
com rewind/forward". Também constrói o substrato de token→DOM que o TTS
sincronizado (Fase 6) vai reaproveitar.
- **Painel de texto completo**, rolável, que aparece/some (drawer/overlay —
  no celular ocupa quase a tela toda; mesma implementação em desktop). DOM
  completo (um `<span>` por token, com `data-idx`) construído uma vez por
  documento e cacheado — não reconstrói a cada abertura.
- **Clique por palavra** → move o ponteiro do RSVP exatamente pra ela. Usar
  *event delegation* (um listener no container, não um por palavra) por
  performance — um doc pode ter dezenas de milhares de tokens. Parágrafos
  visualmente separados (espaçamento), mesmo com clique por palavra.
- **Dois toggles configuráveis** (persistidos, mesmo padrão do toggle de
  ORP): "fechar painel ao clicar" (**padrão: desligado** — painel continua
  aberto) e "pausar ao abrir o painel" (**padrão: desligado** — pode ficar
  aberto durante o play).
- **Palavra atual destacada** no painel, com **auto-scroll em modo "seguir"**
  ativo por padrão (necessário de verdade, já que o padrão permite painel
  aberto durante o play) — desliga quando o usuário rola manualmente, mostra
  botão flutuante "voltar pra posição atual" pra religar.
- **Barra de progresso vira scrubber arrastável** (usa `seekFraction()`, já
  existe no engine; arrastar pausa a reprodução) + **marcadores de parágrafo
  sutis, todos exibidos** (sem lógica de corte por densidade — confirmado
  após mockup visual).
- **Contagem viva durante a leitura**: palavras restantes e tempo restante
  (agora honesto, porque o WPM é efetivo desde a Fase 1.6) — "1.240 / 8.017
  palavras · ~4 min restantes".
- Lacuna de escopo reconhecida: isto é o "Reader/Source view" da análise do
  SwiftRead original, que nunca entrou no spec enxuto. Não é o TOC (capítulos)
  — esse vem como camada extra na Fase 4, quando houver estrutura de verdade.

### [ ] Fase 3 — Progresso e desempenho *(era Fase 5, agora ampliada)*
Duas coisas de formatos de dado diferentes:
- **Posição de leitura** (continuar de onde parou): uma linha por documento
  com o ponteiro atual. Salva ao pausar/sair; restaura ao reabrir. Biblioteca
  compartilhada → uma posição por documento, não por pessoa (a última leitura
  vence — limitação aceita).
- **Sessões de leitura** (tabela nova, event-log — não é `position INTEGER`):
  cada sessão guarda documento, início, fim, palavras avançadas, WPM usado.
  Disso derivam WPM médio ao longo do tempo, palavras lidas por dia, e o que
  mais a gamificação/dashboard (Fase 7) precisar. Estatísticas
  **compartilhadas** (casa como um usuário) — sem tabela de perfis, sem
  seletor de quem lê.
- Definição de sessão (fechada): começa no primeiro play; encerra no fim do
  documento, ao sair do leitor, ou após **5 minutos** de inatividade.
  Detecção via **heartbeat** a cada ~30s enquanto toca (atualiza `ended_at` +
  palavras avançadas), complementado por envio explícito ao
  pausar/sair/minimizar quando o navegador permitir.
- Contra a inflação de "palavras lidas": aceito como limitação (ver
  "Limitações aceitas") — inclui saltos via painel/scrubber sem tentar
  diferenciar "pulei" de "li".
- Agregação por dia usa o fuso local sobre os timestamps ISO (UTC) já
  padronizados na Fase 1.6.

### BLOCO B — Fontes de conteúdo

### [ ] Fase 4 — Import: upload de arquivo + URL *(era Fase 2)*
- Upload: PDF (PyMuPDF/`fitz`), EPUB (`ebooklib`), TXT puro.
- URL: fetch server-side + extração via `trafilatura` — sem headless
  browser; paywall/SPA pesada/anti-bot falham com erro claro, sem contornar.
- `source_type` passa a distinguir `upload | url | paste`; `format` reflete o
  tipo real.
- **TOC (índice de capítulos)** entra aqui como camada sobre o painel da Fase
  2: EPUB tem capítulos/headings nativos; PDF tem outline quando existe.
  Mapear cada capítulo a um índice de token e listar no painel. Texto colado
  continua sem TOC (não tem estrutura), só com navegação por palavra.
- Limitações aceitas: PDF de 2 colunas / muitas notas → ordem bagunçada;
  escaneado (sem texto) fica de fora (sem OCR).

### [ ] Fase 5 — Pastas + busca na biblioteca *(era Fase 6)*
- Pastas/coleções pra organizar (lacuna do SwiftRead original).
- Busca por título/conteúdo (outra lacuna do original).

### BLOCO C — TTS consolidado

### [ ] Fase 6 — TTS sincronizado *(funde as antigas Fases 3 + 10)*
> Fecha "toda a questão do TTS de uma vez", já sincronizado. Discussão de
> detalhe adiada pelo usuário ("falaremos mais sobre isso depois"); aqui só o
> esqueleto e as decisões em aberto.
- **Camada 1 — geração/plumbing** (era a Fase 3 independente): Kokoro-82M via
  Kokoro-FastAPI como serviço Docker na rede do stack de IA existente
  (RTX 5060 Ti). Cache server-side por `(document_id, voice)`. Auto-detecção
  de idioma (`langdetect`) pra voz padrão PT-BR/EN; troca manual por
  documento. Sem fila (sequencial). Tabela `generated_audio`.
- **Camada 2 — sincronização por palavra** (era a Fase 10): highlight
  karaoke reaproveitando o **substrato de token→DOM da Fase 2**. Áudio toca
  num `<audio>` padrão; a palavra falada acende no painel.
- **Decisão-chave em aberto** (a resolver quando chegarmos): de onde vêm os
  timestamps por palavra? Opções — (a) *forced alignment* com Whisper na GPU
  (texto conhecido + áudio → timestamps; viável com a 5060 Ti), (b) saída
  nativa de duração de fonema do Piper, (c) estimativa proporcional por
  comprimento/sílaba (cru/deriva). Cachear os timestamps junto do áudio.
- **UX em aberto**: karaoke no painel de texto (natural, reusa a Fase 2) vs.
  flash do RSVP guiado pelo áudio (a prosódia do TTS ≠ ritmo bom de RSVP).
  A discutir junto com o resto do TTS.

### BLOCO D — Enriquecimento

### [ ] Fase 7 — Dashboard de estatísticas *(era Fase 7)*
- Consome a tabela de sessões da Fase 3: WPM médio no tempo, palavras/dia,
  tempo total, streaks, gráficos — o material pra reforço de hábito.
- Reverte o non-goal original ("no long-term statistics dashboards").

### [ ] Fase 8 — Teste de velocidade/compreensão embutido *(era Fase 8)*
- WPM real (palavras ÷ tempo) + perguntas simples de compreensão, dentro do
  leitor. Reverte o non-goal original ("no comprehension quizzes").

### [ ] Fase 9 — HTTPS local + PWA offline real *(era Fase 9)*
- mkcert pra contexto seguro; service worker (cache de assets, offline,
  "adicionar à tela inicial"). Reverte o "só HTTP puro" original. Fica depois
  do TTS/stats porque é infra, mas ajuda o uso diário/hábito quando vier.

### [ ] Fase 10 — Polish *(era Fase 4)*
- Overlay de atalhos (Shift+?), refinamento de tema, web manifest básico
  (ícone+nome — o service worker é da Fase 9), mDNS via Avahi (`reader.local`)
  com fallback de IP estático documentado (mDNS no Android é inconsistente).

### [ ] Fase 11 (stretch) — Chatterbox-Turbo como segunda engine TTS
- MIT, Resemble AI — narração em inglês mais natural. Só depois do Kokoro
  (Fase 6) rodando de ponta a ponta.

## Limitações aceitas (não resolver a menos que seja pedido)

- PDFs de duas colunas ou com muitas notas de rodapé podem extrair em ordem
  de leitura bagunçada
- Sem fila para gerações de TTS concorrentes — processamento sequencial é
  suficiente em escala doméstica
- Sem proteção contra títulos duplicados de verdade (mitigado: título
  colidente ganha sufixo automático) nem contra uma pessoa apagar um
  documento que outra está lendo
- Sites com paywall, muito JS ou anti-bot vão falhar na extração de URL, sem
  fallback
- Documentos escaneados (PDF sem texto) são ignorados — sem OCR
- Abreviações terminadas em ponto ("Dr.", "Sra.", "etc.") disparam a micro-pausa
  de fim de frase indevidamente — limitação conhecida do tokenizer (ver Fase 1.6
  P2)
- Dedup só pega duplicata exata (mesmo hash); textos quase iguais (espaços ou
  caixa diferentes) entram como documentos separados
- "Palavras lidas" pode inflar: o RSVP avança sozinho, então dar play e sair
  de perto (com o Wake Lock mantendo a tela ligada) conta leitura fantasma.
  Mitigação parcial planejada na Fase 3 (só contar com interação recente); sem
  detecção de atenção de verdade, não dá pra eliminar
- Estatísticas são da casa toda, não por pessoa (biblioteca única sem login) —
  se duas pessoas leem, WPM médio/streak/palavras-por-dia se misturam
