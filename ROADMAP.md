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

## Feedback de uso real — pendente de deliberação (registrado em 2026-07-12)

Uso real do usuário: colou um capítulo inteiro de EPUB (convertido pra TXT)
pra testar a experiência com um texto longo de verdade. Ainda **não
implementado** — só registrado aqui para discutirmos escopo/prioridade na
próxima sessão, antes de qualquer código.

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

**Perguntas em aberto para a próxima sessão:**
1. O painel de "texto original clicável" deveria mostrar o texto corrido
   completo, ou ser estruturado por parágrafo (mais fácil de navegar, exige
   mapear cada parágrafo a um índice de token)?
2. Isso deveria também servir de Table of Contents quando a Fase 2 trouxer
   EPUB/PDF (que têm capítulos/headings de verdade), ou são features
   separadas?
3. "Progresso mais detalhado" é: (a) contagem viva de palavras/tempo restante
   durante a leitura, (b) uma barra com mais granularidade (marcações por
   parágrafo), ou (c) as duas coisas?
4. Isso muda a prioridade da fila? Hoje a ordem é Fase 2 (import) → Fase 5
   (progresso). Dado que o problema relatado é sobre a experiência *central*
   de leitura (não sobre importar mais formatos), faz sentido esse item
   furar a fila como a Fase 1.5/1.6 furaram?
5. Se vamos desenhar o schema de progresso pensando em gamificação/dashboard
   futuros, o que exatamente precisa ser guardado por sessão de leitura (só
   posição final? início/fim de cada sessão? WPM usado? palavras lidas por
   dia)? Vale a pena decidir isso antes de criar a tabela na Fase 5, pra não
   ter que migrar depois.

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

### [ ] Fase 2 — Import: upload de arquivo + URL
- Upload de arquivo: PDF (PyMuPDF/`fitz`), EPUB (`ebooklib`), TXT puro
- Paste de URL: fetch server-side + extração via `trafilatura` — sem
  headless browser na v1, então sites com paywall, SPA pesada de JS ou
  proteção anti-bot vão falhar na extração; mostrar erro claro, sem tentar
  contornar
- PDFs de duas colunas ou com muitas notas de rodapé podem extrair em ordem
  de leitura bagunçada — aceitar, não resolver agora
- Documentos escaneados (PDF sem texto/imagem) ficam de fora — sem OCR na v1
- `source_type` no banco passa a distinguir `upload | url | paste`

### [ ] Fase 3 — TTS narrado (modo independente, não sincronizado)
- Engine padrão: Kokoro-82M via Kokoro-FastAPI, como serviço Docker próprio
  na rede do stack de IA existente
- TTS e RSVP são dois modos de consumo separados e mutuamente exclusivos:
  texto vai pro Kokoro, volta como arquivo de áudio simples, toca num
  `<audio>` HTML padrão — sem highlight sincronizado nessa fase (isso só
  volta na Fase 10)
- Cache de áudio gerado server-side, chaveado por `(document_id, voice)` —
  já que a biblioteca é compartilhada, o áudio de um documento/voz é gerado
  uma vez só e reaproveitado por qualquer um na rede
- Auto-detecção de idioma simples (`langdetect` ou similar) pra escolher voz
  padrão — Kokoro cobre inglês e português brasileiro, que cobre o conteúdo
  misto dessa biblioteca; usuário pode trocar a voz manualmente por
  documento
- Sem fila para gerações concorrentes de TTS — processamento sequencial
  está bom pra escala doméstica
- Tabela `generated_audio` (document_id, voice, file_path, created_at)

### [ ] Fase 4 — Polish
- Atalhos de teclado (Space, setas — já parcialmente feito na Fase 1 — mais
  overlay de ajuda tipo Shift+?)
- Web app manifest básico (ícone + nome, sem service worker ainda — isso é
  Fase 9)
- mDNS via Avahi pra um hostname amigável (`reader.local`); documentar
  fallback de IP estático no README, já que suporte a mDNS no Android é
  inconsistente entre aparelhos — testar nos celulares reais antes de
  depender disso
- Refinamento de tema (contraste, espaçamento)

### [ ] Fase 5 — Biblioteca: progresso de leitura
- Salvar posição de leitura por documento (biblioteca é compartilhada, sem
  usuários — então é uma posição só por documento, não por pessoa)
- "Continuar de onde parou" ao reabrir um documento
- Aceitar como limitação: sem proteção se duas pessoas lerem o mesmo
  documento ao mesmo tempo (a posição salva é a da última leitura)

### [ ] Fase 6 — Pastas + busca na biblioteca
- Pastas/coleções pra organizar documentos (lacuna do SwiftRead original)
- Busca por título/conteúdo na biblioteca (outra lacuna do original)

### [ ] Fase 7 — Estatísticas de longo prazo
- Tempo total lido, palavras lidas, gráfico de evolução de WPM ao longo do
  tempo
- Reverte o non-goal original ("no long-term statistics dashboards")

### [ ] Fase 8 — Teste de velocidade/compreensão embutido
- Mede WPM real (contagem de palavras ÷ tempo) + perguntas simples de
  compreensão sobre o texto lido, dentro do próprio leitor (o SwiftRead
  original só tem isso no site, não no app)
- Reverte o non-goal original ("no comprehension quizzes")

### [ ] Fase 9 — HTTPS local + PWA offline real
- Configurar mkcert pra certificado local, habilitando contexto seguro
- Service worker de verdade: cache de assets, funciona offline, banner de
  "adicionar à tela inicial" completo no Android/iOS
- Reverte a decisão original de servir só HTTP puro

### [ ] Fase 10 — Sync palavra-a-palavra TTS/RSVP via Piper
- Trocar/adicionar Piper como engine de voz mais natural
- Decidir e implementar como conseguir timestamps por palavra (saída nativa
  do Piper vs. alinhamento forçado à parte) — avaliar na hora, não é
  trivial em todos os wrappers
- Usar os timestamps pra sincronizar o highlight do RSVP com a narração
  (karaoke-style)
- Reverte a decisão arquitetural original de manter TTS e RSVP
  independentes

### [ ] Fase 11 (stretch) — Chatterbox-Turbo como segunda engine TTS
- MIT, Resemble AI — narração em inglês com naturalidade maior
- Só começar depois que o Kokoro (Fase 3) estiver funcionando de ponta a
  ponta

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
