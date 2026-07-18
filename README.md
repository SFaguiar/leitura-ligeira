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
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
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

### Ambiente reproduzível

A instalação nativa suportada usa Python >=3.13.11 e <3.14. O arquivo
requirements.lock fixa as 42 dependências diretas e transitivas; requirements.txt
permanece apenas como lista humana das dependências diretas. Antes de iniciar, o
launcher confere a versão do Python e cada pacote instalado.

    .\verificar_ambiente.bat

Baselines e mínimos da Release 1.0:

- Python 3.13.11; pip 25.3 foi usado para gerar e validar o lock.
- Docker Engine 24.0 ou superior e Docker Compose 2.30.0 ou superior.
  O baseline validado foi Engine 29.5.3 e Compose 5.1.4.
- A imagem da aplicação usa Python 3.13.11 slim-bookworm com digest imutável.
- Kokoro-FastAPI 0.6.0 CUDA 12.8 também usa tag e digest imutáveis.
- Ollama é opcional e não bloqueia biblioteca, leitor ou narrador. Para futuras
  perguntas de compreensão, o baseline é Ollama 0.32.0 com qwen3:8b.
- Node 25.2.1 é usado somente pelos testes JavaScript, não em produção.

O inicializador testa primeiro se o Kokoro já está saudável. Somente quando ele
está parado tenta acionar o Docker. Se Docker ou Kokoro estiver indisponível, a
aplicação continua funcionando sem narrador e mostra orientação de diagnóstico.

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

## Backup e restauração

O backup pode ser criado com a aplicação em execução. Ele usa o snapshot
nativo do SQLite, inclui data/app.db e data/secret_key, grava manifesto
versionado com SHA-256 e valida o banco antes de concluir:

    .\backup_leitura_ligeira.bat

O ZIP fica em backups/ e contém documentos, hashes de senha e a chave de
sessão: trate-o como arquivo sensível. O cache TTS e certificados locais não
são incluídos porque podem ser regenerados ou são específicos da máquina.

Para conferir um pacote sem restaurá-lo:

    .venv\Scripts\python.exe scripts\backup_restore.py verify backups\ARQUIVO.zip

A restauração padrão vai para uma pasta limpa, restored-data/, sem tocar na
biblioteca atual:

    .\restaurar_leitura_ligeira.bat backups\ARQUIVO.zip

Depois de conferir a cópia, encerre o servidor antes de substituir os dados
reais. A opção explícita abaixo preserva o diretório anterior com o sufixo
pre-restore, permitindo rollback manual:

    .\restaurar_leitura_ligeira.bat backups\ARQUIVO.zip --target-data-dir data --replace

## Migrações automáticas e rollback

`init_db()` versiona o schema com `PRAGMA user_version`. Antes de alterar um
banco existente, o servidor cria e verifica um backup em
`backups/migrations/`; se o backup falhar, a migração nem começa. A alteração
roda numa transação e só é confirmada depois de `PRAGMA integrity_check` e
`PRAGMA foreign_key_check` passarem. Bancos criados por uma versão futura são
recusados para impedir downgrade acidental.

Para conferir o banco atual manualmente:

    .venv\Scripts\python.exe -c "from app.database import check_database; print(check_database())"

Para desfazer uma migração, encerre o servidor e restaure o ZIP imediatamente
anterior. O diretório migrado ainda será preservado com sufixo `pre-restore`:

    .\restaurar_leitura_ligeira.bat backups\migrations\ARQUIVO.zip --target-data-dir data --replace

Não apague o ZIP até validar login, biblioteca e abertura de um documento. Ele
contém o banco e a chave de sessão e deve ser protegido como dado sensível.

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
