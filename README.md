# Leitura Ligeira

Leitor de leitura rápida self-hosted para a rede de casa. Dois jeitos de ler:
**Focus** (RSVP — palavras piscando em posição fixa, com micro-pausas
inteligentes) e **Flow** (texto completo com a marca acompanhando a palavra —
em formalização). Roda no PC, acessado pelo celular via Wi-Fi como web app
comum.

Backend em Python/FastAPI, frontend em JS puro (sem build step), SQLite como
banco. Veja o [ROADMAP.md](ROADMAP.md) para arquitetura, fases, decisões de
design registradas e as questões em aberto.

## Status (2026-07-12): Fases 1–2 concluídas

O que funciona hoje:

- **Leitor RSVP (Focus):** WPM efetivo 100–1000 (o número do slider é
  throughput real), palavras por vez 1–4 sem cruzar fronteira de
  frase/parágrafo, micro-pausas por pontuação/palavra longa/parágrafo, ORP
  opcional (letra-âncora), shrink-to-fit para palavras longas, tema
  claro/escuro, Wake Lock (tela não apaga lendo), tap para play/pause,
  atalhos de teclado (Espaço, setas), navegação por frase (⏮/⏭).
- **Navegação no texto:** painel com o texto completo — toque em qualquer
  palavra para pular exatamente para ela; palavra atual destacada com
  rolagem automática ("modo seguir"); barra de transporte própria no painel;
  barra de progresso arrastável (scrubber) com marcadores de parágrafo;
  contador vivo de palavras/tempo restante.
- **Biblioteca da casa:** colar texto, dedupe automático por conteúdo,
  renomear/excluir, contagem de palavras e tempo estimado por item.

**A seguir** (ver ROADMAP): modos Focus/Flow formais com WPM independente por
modo; contas da casa com login (senha simples, sem exigência de
complexidade), permissões por documento (dono/concedido/admin), prateleiras
de leitura (quero ler/lendo/lido/abandonado), progresso e estatísticas
individuais; biblioteca compartilhada com opção de documento privado; import
de PDF/EPUB/URL; TTS local sincronizado (Kokoro) nos dois modos.

**Nota sobre WPM:** o número no slider é o throughput *efetivo* — palavras
por minuto reais, já descontando as micro-pausas. Se você calibrou sua
velocidade antes da Fase 1.6 (quando era nominal), recalibre.

## Rodando localmente (sem Docker)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Abra `http://localhost:8000` no PC, ou `http://<IP-do-PC-na-rede>:8000` no
celular (mesma rede Wi-Fi). Descubra o IP com `ipconfig` (Windows) /
`ip addr` (Linux).

### Narrador local (Kokoro)

O backend precisa do Kokoro-FastAPI ouvindo em `127.0.0.1:8880`. Nesta máquina
(RTX 5060 Ti), o Compose usa a imagem oficial CUDA 12.8 fixada na versão 0.6.0:

```bash
docker compose up -d tts
```

Espere `http://localhost:8880/health` responder antes de ligar o narrador. O
primeiro start baixa uma imagem grande e pode levar alguns minutos. No leitor,
a taxa vai de 0.5x a 4.0x, o WPM efetivo permanece visível e o buffer antecipado
pode ser ajustado de 30 a 120 segundos (60s por padrão).
Quem roda o FastAPI nativamente não precisa configurar variável alguma; o
default já é `http://localhost:8880`. Dentro do Compose, `KOKORO_URL` é definido
como `http://tts:8880` automaticamente.

## Rodando com Docker Compose

```bash
docker compose up --build
```

O banco fica em `./data/app.db` (montado como volume) — fazer backup é copiar
um arquivo.

## Limitações conhecidas

- **Sem HTTPS por enquanto.** HTTP puro na LAN; certificado local (mkcert) e
  PWA offline vêm numa fase futura. Sem contexto seguro, o Android não
  oferece o banner completo de "instalar app", mas tudo funciona na aba do
  navegador.
- **Login sem exigência de senha complexa** (quando as contas chegarem): é
  ambiente doméstico, cada um escolhe a própria senha. A senha ainda trafega
  em HTTP puro até a fase de HTTPS — aceitável numa LAN de confiança.
- Hostname amigável via mDNS (`reader.local`) está planejado, mas o suporte
  no Android é inconsistente — o caminho garantido é o IP fixo do PC.
- Lista completa de limitações aceitas (e o porquê de cada uma) no
  [ROADMAP.md](ROADMAP.md).

## Licença

[AGPL-3.0](LICENSE). Uso comercial e oferecer como SaaS são permitidos, mas
qualquer versão modificada disponibilizada para terceiros — inclusive só via
rede/SaaS, sem distribuir o binário — precisa ter seu código-fonte aberto sob
a mesma licença. Ninguém pode pegar este projeto e fechá-lo.
