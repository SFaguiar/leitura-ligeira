# Declaração provisória de acessibilidade

Última revisão: 18 de julho de 2026.

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
- zoom permitido, alvos principais de 44 × 44 CSS px, foco visível e respeito a
  `prefers-reduced-motion`;
- teste estático de contratos e auditoria renderizada com axe-core 4.12.1.

## Avaliação realizada

Em 18 de julho de 2026, o gate automatizado auditou 16 combinações de
estado/skin em Edge headless: login, criação de perfil, biblioteca vazia,
importação, leitor Foco, leitor Fluxo, Sistema e diálogo de atalhos. O axe-core
não encontrou violações. Contratos adicionais verificam IDs e referências ARIA,
nomes de campos, ordem de headings, controles nativos, erros e regiões vivas.

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

A revisão profunda de reflow/zoom, contraste forçado e mobilidade pertence ao
R10. OpenDyslexic, Leitura Biônica, Modo Zen e demais adaptações cognitivas
pertencem ao R11. Equivalência visual de todo feedback sonoro pertence ao R12.
A internacionalização e o inglês padrão pertencem ao R13. Por isso, esta versão
ainda não deve ser apresentada como plenamente conforme às WCAG.

## Relatar uma barreira

Abra uma issue no
[repositório do projeto](https://github.com/SFaguiar/leitura-ligeira/issues)
com a tela, a ação tentada, navegador, sistema operacional, tecnologia
assistiva e versão utilizada. Não inclua senha, cookie, documento privado nem
outro dado pessoal. Barreiras que impeçam uma função essencial são tratadas como
bloqueadoras da Release 1.0.