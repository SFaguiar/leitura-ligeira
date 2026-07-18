# Leitura Ligeira

Leitor de leitura rápida self-hosted para o computador e a rede doméstica.
Oferece **Foco** (RSVP em posição fixa), **Fluxo** (texto completo com marcação
sincronizada) e **Narrador** local via Kokoro. A biblioteca organiza textos,
PDF, EPUB e páginas web por busca, coleções e prateleiras, com perfis separados.

Backend em Python/FastAPI, frontend em HTML, CSS e JavaScript puro, SQLite como
banco e nenhum build step. Veja o [ROADMAP.md](ROADMAP.md) para decisões e a
sequência da Release 1.0.

## Status (2026-07-18): missão Release 1.0

O produto está funcionalmente congelado e atravessou os gates R1–R8. Hoje há:

- leitura Foco/Fluxo com progresso, navegação por texto/capítulos, ORP,
  controles independentes, Wake Lock e atalhos de teclado;
- narração Kokoro sincronizada de 0,5× a 4,0×, vozes identificadas por idioma,
  buffer configurável e degradação segura quando o serviço não está disponível;
- perfis com sessão revogável, documentos privados/da casa, importação
  TXT/PDF/EPUB/URL, busca reativa, coleções e prateleiras;
- estatísticas opt-in, duas skins, tema claro/escuro, onboarding e estados
  acionáveis de carregamento, vazio e erro;
- tela **Sistema** com versão, banco, transporte, Kokoro, Ollama e indicação do
  que é essencial ou opcional;
- HTTPS local opcional, backup/restauração verificável, ambiente congelado,
  migrações transacionais, hardening OWASP e um gate automatizado de release.

A release internacional agora exige os gates R9–R14: leitores de tela e
semântica; baixa visão/mobilidade; neurodiversidade; equivalência auditiva;
internacionalização com novo nome e inglês padrão; e auditoria humana final.
O próximo gate é **R9 — tecnologias assistivas**. A versão `1.0.0-rc1` só será
gerada no R14, depois da tradução/rebranding do R13.

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
está parado tenta acionar o Docker. A solicitação de startup ocorre em segundo
plano: se Docker ou Kokoro estiver indisponível ou ainda carregando, biblioteca,
Foco e Fluxo abrem normalmente e o botão do Narrador oferece uma nova tentativa.

### Modo degradado e diagnóstico

Docker, Kokoro, Ollama e internet são dependências opcionais. A aplicação e o
SQLite iniciam de forma independente; a ausência do Kokoro desativa apenas a
narração e nunca esconde os controles normais de WPM/chunk. Falhas de descoberta
de vozes ficam em cache por 10 segundos para evitar esperas e requisições
repetidas, e a interface mostra uma mensagem recuperável.

O diagnóstico local consolidado pode ser executado sem iniciar o servidor:

```powershell
.\verificar_ambiente.bat
```

Com o servidor ativo, `GET /system/health` é uma sonda pública mínima para
aplicação/SQLite. `GET /system/diagnostics` exige login e informa versão,
integridade do banco, Kokoro, Ollama, HTTP/HTTPS e se internet é necessária,
sem expor caminhos locais ou detalhes de exceções.

### Gate de release

Antes de publicar ou aceitar uma alteração como candidata à release, execute:

```powershell
.\verificar_release.bat
```

O comando valida o lock do ambiente, roda toda a suíte Python, compila os
módulos, executa `pip check`, verifica a sintaxe JavaScript, os contratos entre
HTML/CSS/JS, acessibilidade/contraste/reflow essenciais, a regressão do driver
TTS, um soak determinístico de 6.000 tokens em 4x, o Compose e a integridade do
SQLite. O processo retorna código diferente
de zero na primeira falha e grava um relatório JSON atômico em
`release-reports/`. Em uma máquina deliberadamente sem Docker, use
`.\verificar_release.bat --skip-docker`; todos os demais gates continuam
obrigatórios.

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

## Primeiros passos na interface

1. Crie um perfil e use uma frase-senha exclusiva com pelo menos 8 caracteres.
2. Em **+ Novo texto**, cole conteúdo ou escolha arquivo/URL. A tela vazia da
   biblioteca também conduz por esses passos.
3. Abra o documento e escolha **Foco**, **Fluxo** ou **Narrador**. Velocidade,
   fonte, voz e buffer podem ser calibrados durante a leitura.
4. Use **Sistema** para conferir a saúde local. Falhas de Kokoro/Ollama são
   opcionais; banco ou aplicação indisponíveis exigem correção antes de ler.

Pressione `Shift+?` ou use o botão **Atalhos** para abrir a referência de
teclado. `Tab` percorre controles, `Enter`/`Espaço` acionam itens focados e o
scrubber aceita setas, `Page Up/Down`, `Home` e `End`. Os diálogos prendem o foco
enquanto abertos e `Esc` os fecha. O navegador também pode oferecer **Instalar
aplicativo/Adicionar à tela inicial** graças ao manifest; isso cria um atalho,
mas o modo offline completo permanece planejado para depois da release.

## Rodando com Docker Compose

```bash
docker compose up --build
```

O banco fica em `./data/app.db` (montado como volume). O Compose mantém a
aplicação em loopback por padrão; defina `LEITURA_BIND_ADDRESS=0.0.0.0` somente
para exposição deliberada à LAN. A pasta `./certs` é montada como somente leitura.

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

## Atualização segura

Antes de atualizar, encerre o servidor e crie um backup verificável:

```powershell
.\backup_leitura_ligeira.bat
.\verificar_release.bat
```

Em uma instalação Git sem alterações locais de produção:

```powershell
git pull --ff-only
.venv\Scripts\python.exe -m pip install -r requirements.lock
.\verificar_ambiente.bat
.\iniciar_leitura_ligeira.bat
```

A primeira inicialização aplica migrações somente depois de criar um backup
pré-migração verificado. Confirme login, biblioteca e abertura de um documento;
depois execute `.\verificar_release.bat`. Se houver regressão de dados,
encerre o servidor e restaure o ZIP pré-migração conforme a seção anterior. Não
faça downgrade de código sobre um banco com `user_version` mais novo.

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

## Hardening de segurança

A R6 adiciona sessão revogável no servidor, proteção CSRF, limitação de login,
validação estrita de Host e payloads, CSP/headers defensivos, logs de segurança
e importações endurecidas contra arquivos hostis e SSRF. A documentação do
modelo de ameaça e o mapeamento OWASP Top 10:2025 estão em
[SECURITY.md](SECURITY.md).

A primeira abertura após atualizar para a R6 pode pedir login novamente: o
cookie antigo não possui o token server-side exigido agora. Novas senhas têm
entre 8 e 256 caracteres; hashes PBKDF2 antigos são atualizados automaticamente
no próximo login válido.

Eventos relevantes são gravados em `data/logs/security.log`, com rotação e sem
senhas/cookies. Para aceitar um hostname adicional:

```powershell
$env:LEITURA_ALLOWED_HOSTS = 'leitor.casa'
```

O Docker mantém a porta da aplicação em loopback e roda sem root, capabilities
ou escrita fora de `/app/data` e `/tmp`. Exposição deliberada pelo Compose:

```powershell
$env:LEITURA_BIND_ADDRESS = '0.0.0.0'
docker compose up -d
```

## Solução de problemas

- **Porta 8000 ocupada:** o inicializador distingue outra instância do Leitura
  Ligeira de um programa estranho. Encerre a instância anterior ou use
  `.\iniciar_leitura_ligeira.bat --port 8001`.
- **`SSL_ERROR_RX_RECORD_TOO_LONG`:** o navegador abriu `https://` enquanto o
  servidor está em HTTP. Use exatamente a URL mostrada pelo inicializador ou
  configure o par de certificados; `--no-https` força o modo HTTP.
- **Narrador indisponível/HTTP 500:** a leitura Foco/Fluxo continua funcionando.
  Confira `docker compose ps`, depois `docker compose logs --tail 100 tts` e use
  **Tentar Narrador** após o contêiner ficar saudável.
- **Docker não inicia:** abra o Docker Desktop e aguarde o Engine. O aplicativo
  nativo ainda pode ser iniciado sem narrador; Kokoro não bloqueia a biblioteca.
- **Ollama indisponível:** nenhuma função da Release 1.0 depende dele. O estado
  aparece como opcional na tela **Sistema**.
- **Banco ou aplicação degradados:** abra **Sistema**, atualize o diagnóstico e
  rode `.\verificar_ambiente.bat`. Faça backup antes de qualquer restauração;
  use `check_database()` da seção de migrações para confirmar integridade.
- **Interface desatualizada após upgrade:** recarregue ignorando o cache
  (`Ctrl+F5`). Se o problema persistir, confirme a versão exibida em **Sistema**
  e execute o gate de release.

## Limitações conhecidas

- **HTTP continua disponível para LAN confiável.** As demais proteções da
  aplicação não cifram o tráfego; use o HTTPS opcional para redes
  compartilhadas ou quando quiser proteger senha, cookie e documentos.
- **Senha sem regras de composição:** novas senhas exigem 8–256 caracteres,
  mas não impõem símbolos; são armazenadas com PBKDF2 e salt individual.
- Hostname amigável via mDNS (`reader.local`) está planejado, mas o suporte
  no Android é inconsistente — o caminho garantido é o IP fixo do PC.
- Lista completa de limitações aceitas (e o porquê de cada uma) no
  [ROADMAP.md](ROADMAP.md).

## Licença

[AGPL-3.0](LICENSE). Uso comercial e oferecer como SaaS são permitidos, mas
qualquer versão modificada disponibilizada para terceiros — inclusive só via
rede/SaaS, sem distribuir o binário — precisa ter seu código-fonte aberto sob
a mesma licença. Ninguém pode pegar este projeto e fechá-lo.
