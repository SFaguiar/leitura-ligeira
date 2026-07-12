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

## Fase 1.6 — Hardening da fundação (P0 implementado, 2026-07-12)

Fruto da revisão profunda das Fases 1 e 1.5. Objetivo: fechar as lacunas de
base **antes** da Fase 2, porque é a parte onde o usuário passa mais tempo e o
custo de mudar depois é maior. P0 implementado e aguardando teste manual do
usuário (checklist enviado); P1/P2 seguem planejados, não iniciados.

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

### P1 — robustez
- [ ] `PRAGMA journal_mode=WAL` + `busy_timeout` no SQLite (evita "database is
      locked" com vários celulares lendo/gravando — casa com o uso
      multi-dispositivo das Fases 3 e 5)
- [ ] Data em ISO com `T` vinda do backend (o `created_at + "Z"` atual funciona
      no Chrome/Android mas pode dar "Invalid Date" no Safari/iOS)
- [ ] Guardar `word_count` na inserção; mostrar palavras + tempo estimado por
      item na biblioteca (é onde o usuário decide o que ler; também alimenta a
      Fase 7 de graça)
- [ ] Palavra muito longa: shrink-to-fit (reduzir a fonte quando não couber em
      uma linha) para preservar a ilusão de posição fixa do RSVP
- [ ] Limite de tamanho em `raw_text`/`title` + erro amigável (um paste/PDF
      gigante vira um blob único carregado inteiro no navegador)
- [ ] Modal: fechar com Esc e clique no fundo; Enter salva
- [ ] Schema já pronto para o futuro: coluna `lang` (pré-stage do TTS da Fase 3)
      e FK `document_id` com `ON DELETE CASCADE` nas tabelas de áudio/progresso
      (evita órfãos quando a exclusão da Fase 1.5 encontrar esses dados)

### P2 — documentar como limitação / adiar
- [ ] Abreviações ("Dr.", "Sra.", "etc.", "p.ex.") geram falsa pausa de fim de
      frase — limitação conhecida, heurística de correção é arriscada; não
      resolver agora
- [ ] Micro-pausas configuráveis por UI — settings futuro
- [ ] ORP com pivô fixo (letra-âncora) — fora do escopo por decisão do spec

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
