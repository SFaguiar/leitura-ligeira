# Leitura Ligeira

Leitor de leitura rápida self-hosted para a rede de casa. Dois jeitos de ler:
**Focus** (RSVP — palavras piscando em posição fixa, com micro-pausas
inteligentes) e **Flow** (texto completo com a marca acompanhando a palavra —
em formalização). Roda no PC, acessado pelo celular via Wi-Fi como web app
comum.

Backend em Python/FastAPI, frontend em JS puro (sem build step), SQLite como
banco. Veja o [ROADMAP.md](ROADMAP.md) para arquitetura, fases, decisões de
design registradas e as questões em aberto.

## Status (2026-07-18): missão Release 1.0

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

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
iniciar_leitura_ligeira.bat
```

O modo padrão abre somente em `http://127.0.0.1:8000`; outros aparelhos não
conseguem acessar. Para expor explicitamente na rede doméstica:

```powershell
iniciar_leitura_ligeira.bat --lan
```

O inicializador mostra o endereço da rede. Descubra o IP manualmente com
`ipconfig` se necessário. HTTP não cifra senha, cookie ou documentos em
trânsito: use `--lan` somente em Wi-Fi doméstico confiável, nunca em rede
pública, e não encaminhe a porta no roteador.

O runner também pode ser chamado diretamente:

```powershell
.venv\Scripts\python.exe scripts\run_server.py --help
```

Ele rejeita `0.0.0.0` sem `--lan`, desativa confiança em proxy headers e
valida todo par de certificado/chave antes de abrir a porta.
Se a porta já contiver uma instância compatível do Leitura Ligeira, o runner
informa a URL e encerra sem erro. Para outro programa ou modo de transporte,
ele explica o conflito antes do Uvicorn; escolha outra porta com --port 8001.

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

O banco fica em `./data/app.db` (montado como volume). O Compose expõe a
aplicação à LAN deliberadamente e monta `./certs` como somente leitura.

## HTTPS local opcional

HTTPS não é obrigatório para uso no próprio PC ou numa LAN doméstica
estritamente confiável. Quando certificado e chave são configurados, o mesmo
inicializador ativa TLS e marca o cookie de sessão como `Secure`.

Instale o mkcert no Windows e crie a autoridade local:

```powershell
winget install FiloSottile.mkcert
mkcert -install
```

Gere um certificado incluindo todos os nomes realmente usados para acessar o
servidor. Substitua `192.168.1.50` pelo IP do computador:

```powershell
New-Item -ItemType Directory -Force certs
mkcert -cert-file certs\leitura-ligeira.pem -key-file certs\leitura-ligeira-key.pem localhost 127.0.0.1 ::1 192.168.1.50 reader.local
iniciar_leitura_ligeira.bat --lan
```

Os nomes padrão acima são detectados automaticamente. Para outro par:

```powershell
iniciar_leitura_ligeira.bat --lan --certfile C:\certs\server.pem --keyfile C:\certs\server-key.pem
```

Para forçar HTTP mesmo quando os arquivos padrão existirem, use
`iniciar_leitura_ligeira.bat --no-https`.

Cada celular precisa confiar na CA do mkcert para remover o alerta do
navegador. Android exige instalar a CA nas configurações de segurança; iOS
exige instalar o perfil e ativar "Confiança Total" em
`Ajustes > Geral > Sobre > Ajustes de Confiança do Certificado`. Não copie a
chave privada para o celular.

O programa não cria regra de firewall automaticamente. Se o Windows pedir
permissão, autorize somente para redes privadas. Uma regra explícita pode ser
criada em PowerShell administrativo:

```powershell
New-NetFirewallRule -DisplayName "Leitura Ligeira" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private
```

## Limitações conhecidas

- **HTTP continua disponível para LAN confiável.** As demais proteções da
  aplicação não cifram o tráfego; use o HTTPS opcional para redes
  compartilhadas ou quando quiser proteger senha, cookie e documentos.
- **Login sem exigência de senha complexa:** é ambiente doméstico, cada um
  escolhe a própria senha. Ela continua armazenada com hash forte.
- Hostname amigável via mDNS (`reader.local`) está planejado, mas o suporte
  no Android é inconsistente — o caminho garantido é o IP fixo do PC.
- Lista completa de limitações aceitas (e o porquê de cada uma) no
  [ROADMAP.md](ROADMAP.md).

## Licença

[AGPL-3.0](LICENSE). Uso comercial e oferecer como SaaS são permitidos, mas
qualquer versão modificada disponibilizada para terceiros — inclusive só via
rede/SaaS, sem distribuir o binário — precisa ter seu código-fonte aberto sob
a mesma licença. Ninguém pode pegar este projeto e fechá-lo.
