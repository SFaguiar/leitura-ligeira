# Declaração provisória de acessibilidade

Última revisão: 22 de julho de 2026.

O Leitura Ligeira pretende atender às WCAG 2.2 nos níveis A e AA. Esta é uma
declaração provisória de trabalho, não uma alegação de conformidade. A
conformidade só poderá ser declarada após os gates R9–R14 e a avaliação humana
final descrita no ROADMAP.

## Escopo avaliado

A avaliação atual cobre a aplicação web local em português do Brasil, nas skins
Biblioteca e Odysseus, em tema claro e escuro quando aplicável. Inclui login,
criação de perfil, biblioteca, importação, busca, coleções e prateleiras, leitor
nos modos Foco e Fluxo, Narrador, atalhos, diagnóstico do Sistema, dashboard,
diálogos, erros e logout.

O modo Foco apresenta texto rapidamente e não envia cada palavra para a região
falada, evitando sobrecarregar leitores de tela. O modo Fluxo oferece o mesmo
conteúdo como texto contínuo e é a alternativa semântica recomendada para
tecnologias assistivas. Reprodução, pausa e navegação continuam disponíveis nos
dois modos.

## Recursos já implementados

- marcos HTML, títulos, botões nativos, nomes acessíveis e relações entre campos
  e mensagens de erro;
- link para pular ao conteúdo, foco restaurado em diálogos, contenção de foco e
  fechamento por Escape;
- estados `busy`, `expanded`, `selected` e
  `pressed` expostos aos leitores;
- anúncios pontuais de tela, reprodução, pausa, navegação e conclusão, sem
  anunciar o contador que muda a cada palavra;
- navegação por teclado nas abas, controles de leitura, capítulos e scrubber;
- zoom permitido, reflow protegido em 1280, 640 e 320 CSS px, alvos principais
  de pelo menos 48 × 48 CSS px, foco visível não obscurecido e respeito a
  `prefers-reduced-motion`;
- opção por dispositivo “Alta legibilidade”, com superfícies sem textura e pares
  essenciais que miram 7:1, sem alegação de conformidade AAA integral;
- suporte explícito a `forced-colors`, espaçamento de texto definido pelo usuário,
  estados com texto/forma além de cor e alternativa de teclado ao arrasto do
  scrubber;
- preferências por perfil para OpenDyslexic local, coluna, altura/espaçamento,
  guia de leitura, miras ORP e baixa estimulação; todas têm padrão conservador,
  são opt-in e reversíveis;
- Leitura Biônica somente no modo Fluxo: sua marca visual é escondida da árvore
  acessível e cada palavra contínua mantém uma única alternativa de texto;
- Modo Zen, que mantém sair e pausar/reproduzir acessíveis enquanto oculta
  contadores, progresso e ações secundárias;
- teste estático de contratos e auditoria renderizada com axe-core 4.12.1.

## Avaliação realizada

Em 22 de julho de 2026, o gate automatizado auditou 24 combinações de
estado/skin/emulação em Edge headless: os oito estados principais nas duas skins,
login com Alta legibilidade, diálogo de atalhos com `forced-colors` e os novos
estados Fluxo com preferências neurodiversas e Modo Zen. Em cada combinação, o
reflow foi medido em 1280, 640 e 320 CSS px — equivalentes aos cenários de 100%,
200% e 400% partindo de 1280 px — totalizando 72 medições sem rolagem horizontal
da página. O axe-core não encontrou violações e a árvore acessível do Edge não
teve controle sem nome. Contratos adicionais verificam IDs e referências ARIA,
nomes de campos, ordem de headings, controles nativos, erros, regiões vivas, os
pares de contraste mantidos no código e a fonte local licenciada.

Automação não detecta todos os problemas de acessibilidade. A matriz manual em
[ACCESSIBILITY_TESTING.md](ACCESSIBILITY_TESTING.md) ainda precisa ser executada
com NVDA, JAWS, VoiceOver e TalkBack antes de fechar o R9.

## Compatibilidade assistiva

| Combinação | Estado atual |
|---|---|
| Edge no Windows, árvore de acessibilidade e axe-core | Automação aprovada |
| NVDA com Edge/Firefox no Windows | Pendente; NVDA não está instalado na máquina de desenvolvimento |
| JAWS com Edge/Chrome no Windows | Pendente; JAWS não está instalado na máquina de desenvolvimento |
| VoiceOver com Safari no macOS e iOS | Pendente em equipamento Apple |
| TalkBack com Chrome no Android | Pendente em aparelho Android |

## Limitações conhecidas

A validação humana de alto contraste do sistema, zoom real do navegador,
simulações de daltonismo e tecnologias motoras (switch scanning, Voice Access e
rastreamento ocular) continua pendente no R10. O roteiro cognitivo de R11 ainda
precisa validar sessões longas, Leitura Biônica/OpenDyslexic/Zen com TTS e
velocidades altas em usuários e tecnologias assistivas reais. Equivalência visual
de todo feedback sonoro pertence ao R12. A internacionalização e o inglês padrão
pertencem ao R13. Por isso, esta versão ainda não deve ser apresentada como
plenamente conforme às WCAG.

## Relatar uma barreira

Abra uma issue no
[repositório do projeto](https://github.com/SFaguiar/leitura-ligeira/issues)
com a tela, a ação tentada, navegador, sistema operacional, tecnologia
assistiva e versão utilizada. Não inclua senha, cookie, documento privado nem
outro dado pessoal. Barreiras que impeçam uma função essencial são tratadas como
bloqueadoras da Release 1.0.
