# Leitura Ligeira

Leitor RSVP (speed-reading) self-hosted, single-user, sem login. Rodando na
rede local para acesso via celular pelo Wi-Fi de casa.

Backend em Python/FastAPI, frontend em JS puro (sem build step), SQLite como
banco. Veja o [ROADMAP.md](ROADMAP.md) para a arquitetura completa, as fases
planejadas e as decisões de design registradas ao longo do caminho.

## Status: Fase 1 + 1.5 + 1.6 (P0)

RSVP engine (modo Focus), player, import por paste de texto, e CRUD básico da
biblioteca (renomear/excluir documentos). Sem upload de arquivo, URL ou TTS
ainda (fases seguintes — ver ROADMAP.md).

**Nota sobre WPM (mudou na Fase 1.6):** o número no slider agora é o
throughput *efetivo* — palavras/min reais, já descontando o tempo das
micro-pausas. Antes era nominal (a taxa-base entre pausas, ~15–25% acima do
throughput real). Se você tinha calibrado sua velocidade confortável antes
dessa mudança, recalibre — o mesmo número agora lê mais devagar de verdade.

## Rodando localmente (sem Docker)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Abra `http://localhost:8000` no PC, ou `http://<IP-do-PC-na-rede>:8000` no
celular (mesma rede Wi-Fi).

## Rodando com Docker Compose

```bash
docker compose up --build
```

## Limitações conhecidas (Fase 1)

- **Sem HTTPS.** O app é servido em HTTP puro na LAN. Isso é intencional por
  enquanto — nada de certificado self-signed ou mkcert até uma fase futura
  decidir habilitar PWA offline de verdade.
- **Sem autenticação.** Biblioteca única, compartilhada, sem contas — por
  design.
- Descubra o IP do PC na rede local com `ipconfig` (Windows) e use esse IP no
  celular. Um hostname amigável via mDNS (`reader.local`) está planejado para
  uma fase futura, mas o suporte a mDNS no Android é inconsistente — teste no
  aparelho real antes de depender disso.

## Licença

[AGPL-3.0](LICENSE). Uso comercial e oferecer como SaaS são permitidos, mas
qualquer versão modificada disponibilizada para terceiros — inclusive só via
rede/SaaS, sem distribuir o binário — precisa ter seu código-fonte aberto sob
a mesma licença. Ninguém pode pegar este projeto e fechá-lo.
