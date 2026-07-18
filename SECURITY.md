# Política de segurança

O Leitura Ligeira é uma aplicação local e auto-hospedada. O modelo padrão é um
único servidor doméstico acessível em loopback; exposição à LAN exige uma opção
explícita. HTTPS local é opcional, mas recomendado sempre que a rede não for
inteiramente confiável.

Este documento registra o hardening da R6 com base no
[OWASP Developer Guide](https://devguide.owasp.org/) e no
[OWASP Top 10:2025](https://owasp.org/Top10/2025/). Segurança não é uma garantia
absoluta: os controles abaixo reduzem o risco dentro do modelo doméstico e as
limitações residuais ficam declaradas ao final.

## Modelo de ameaça

Ativos protegidos: senhas, sessões, documentos privados, progresso, banco e
chaves locais. Entradas não confiáveis incluem todo corpo/query/header HTTP,
nomes e conteúdo de uploads, URLs importadas, respostas remotas e metadados do
cache TTS. As fronteiras são navegador ↔ FastAPI, FastAPI ↔ SQLite, importador
↔ internet e aplicação ↔ Kokoro.

Assume-se controle administrativo da máquina hospedeira. Não se assume que uma
aba do navegador, um cliente na LAN, um arquivo importado ou um site remoto
sejam confiáveis.

## Controles por risco OWASP Top 10:2025

| Risco | Controles implementados |
|---|---|
| A01 — Broken Access Control | `user_id` deriva somente da sessão; documentos privados retornam 404 para terceiros; progresso e sessões validam proprietário e limites do documento; CSRF obrigatório em toda mutação; Host validado; importação bloqueia endereços não públicos e redirecionamentos perigosos. |
| A02 — Security Misconfiguration | OpenAPI/Swagger/Redoc desligados; CORS não é aberto; CSP e headers defensivos em todas as respostas; bind padrão em loopback; Uvicorn omite headers de servidor; contêiner não-root, read-only, sem capabilities e com `no-new-privileges`. |
| A03 — Software Supply Chain Failures | `requirements.lock` fixa dependências diretas e transitivas; imagens Python e Kokoro usam versão e digest imutáveis; o diagnóstico detecta drift; Dependabot monitora semanalmente pacotes Python e imagens. Atualizações ainda exigem revisão e execução dos gates. |
| A04 — Cryptographic Failures | PBKDF2-HMAC-SHA256 com salt individual e 600.000 iterações; hashes legados são elevados no próximo login; chave de assinatura é aleatória, criada atomicamente e protegida no filesystem; cookie é HttpOnly/SameSite e recebe Secure em HTTPS. |
| A05 — Injection | SQLite usa parâmetros para valores; schemas recusam campos extras e limitam tipos, enums, comprimentos e intervalos; conteúdo apresentado no frontend passa por APIs de texto; CSP reduz o impacto de XSS. |
| A06 — Insecure Design | Default deny para rotas autenticadas e CSRF; operações GET não alteram progresso; uploads têm allowlist, assinatura, MIME, tamanho e inspeção ZIP; recursos remotos possuem timeout, limite de bytes e redirects. |
| A07 — Authentication Failures | Sessões aleatórias ficam armazenadas somente como SHA-256 no banco, são rotacionadas no login e revogadas no logout; login tem limite por conta e IP, resposta genérica e trabalho criptográfico também para usuário inexistente; senhas novas têm 8–256 caracteres. |
| A08 — Software or Data Integrity Failures | Migrações exigem backup verificado, transação e checks do SQLite; restauração verifica manifesto e SHA-256; caminho de áudio TTS é resolvido dentro do cache permitido. |
| A09 — Security Logging and Alerting Failures | Eventos de autenticação, rejeições e exceções são gravados como JSON Lines com rotação em `data/logs/security.log`; valores são normalizados, credenciais não são registradas e cada resposta possui request ID. |
| A10 — Mishandling of Exceptional Conditions | Handler global retorna erro genérico e request ID, nunca traceback; conexões fecham em `finally`; importações têm timeouts e limites; falhas de dependências locais permanecem recuperáveis; testes cobrem exceção inesperada e entradas hostis. |

## Sessões, CSRF e hosts

O cookie `ll_session` contém um token aleatório dentro de um envelope assinado.
No SQLite fica apenas o SHA-256 desse token, associado ao usuário e a uma
expiração. Reiniciar a aplicação não revoga sessões; logout e novo login
revogam/rotacionam o token atual. Cookies antigos da implementação sem sessão
server-side deixam de autenticar e exigem novo login.

Toda requisição mutável (`POST`, `PUT`, `PATCH`, `DELETE`) precisa enviar o
header `X-CSRF-Token` com o valor obtido em `GET /security/csrf`. O frontend faz
isso centralmente. O servidor aceita apenas hosts locais conhecidos; nomes
adicionais podem ser declarados, separados por vírgula:

```powershell
$env:LEITURA_ALLOWED_HOSTS = 'leitor.casa'
```

A aplicação não habilita CORS. Clientes web devem usar a mesma origem. IPs
privados são aceitos apenas quando o runner usa `--lan`; o allowlist adicional
serve para nomes DNS locais personalizados.

## Operação segura

- Prefira `iniciar_leitura_ligeira.bat`; o bind padrão é `127.0.0.1`.
- Para LAN, use `--lan` e HTTPS quando a rede não for totalmente confiável.
- No Compose, a aplicação continua presa ao loopback. Para exposição explícita:

```powershell
$env:LEITURA_BIND_ADDRESS = '0.0.0.0'
docker compose up -d
```

- Proteja `data/`, `backups/` e a chave TLS como dados sensíveis.
- Consulte `data/logs/security.log` após bloqueios, falhas repetidas ou erros
  com request ID. O log gira em três arquivos de até 2 MiB.
- Execute os testes e `pip check` antes de qualquer atualização de dependência.

## Limitações residuais aceitas

- HTTP continua disponível para loopback e LAN doméstica confiável; ele não
  protege senha, cookie ou documentos contra captura na rede.
- Auto-registro e a lista pública de nomes de perfil permanecem decisões de UX
  doméstica. Não exponha a aplicação diretamente à internet.
- O limitador de login é em memória, por processo; reinicia com o servidor e
  não substitui firewall ou reverse proxy em exposição adversarial.
- Não há MFA, recuperação remota de conta nem bloqueio administrativo.
- Logs locais não são enviados a um SIEM e não são à prova de adulteração por
  um administrador da máquina. Artefatos de release ainda não são assinados;
  isso permanece como gate da R9.
- CSP mantém `style-src 'unsafe-inline'` porque a interface vanilla ainda usa
  estilos inline dinâmicos; scripts inline continuam proibidos.

## Relato de vulnerabilidade

Não publique credenciais, banco, documentos ou chaves em uma issue. Abra um
relato privado ao mantenedor com versão/commit, pré-condições, impacto e passos
mínimos de reprodução. Se um canal privado não estiver disponível, abra apenas
uma issue sem detalhes sensíveis pedindo contato seguro.