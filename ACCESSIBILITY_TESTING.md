# Matriz de avaliação assistiva — R9 e R10

Esta matriz segue a separação recomendada entre verificações automáticas e
avaliação humana. Um resultado automatizado aprovado não substitui a execução
dos fluxos reais com tecnologia assistiva.

## Baseline automatizado

Execute a partir da raiz do projeto:

```powershell
npm ci
.\verificar_release.bat
```

O passo `frontend-screenreader` verifica contratos estáticos. O passo
`frontend-axe` inicia Uvicorn e Edge/Chrome em uma cópia temporária,
usa um banco descartável, percorre oito estados nas duas skins e grava o
relatório sanitizado em
`release-reports/r9-axe-latest.json`. O gate falha para qualquer
achado axe de impacto `serious` ou `critical`.

## Combinações humanas obrigatórias

| Família | Navegador mínimo | Plataforma | Estado |
|---|---|---|---|
| NVDA | Edge e Firefox atuais | Windows 11 | Não executado; software ausente |
| JAWS | Edge e Chrome atuais | Windows 11 | Não executado; software ausente |
| VoiceOver | Safari atual | macOS e iOS | Não executado; equipamento externo |
| TalkBack | Chrome atual | Android | Não executado; aparelho externo |

A versão exata de sistema, navegador e tecnologia assistiva deve ser registrada
junto à evidência. A execução é reprovada se uma função essencial não puder ser
descoberta, compreendida ou concluída sem visão.

## Roteiro obrigatório por combinação

1. Abrir a aplicação, usar o link “Ir para o conteúdo principal” e confirmar os
   marcos, o título da página e a lista de perfis.
2. Criar um perfil, provocar cada erro de validação e confirmar que o campo
   inválido e sua mensagem são anunciados sem perder o foco.
3. Fazer logout e login; verificar nomes dos botões, estado ocupado e retorno de
   foco ao fechar os diálogos com Escape.
4. Importar por texto, arquivo e URL; percorrer as abas com setas, criar um erro
   em cada origem e concluir pelo menos uma importação.
5. Buscar, filtrar por coleção e navegar por Todas, Quero ler, Lendo, Lido e
   Abandonado. Confirmar o modal de três escolhas de um item abandonado.
6. Abrir um documento, identificar título, modos e controles. Reproduzir,
   pausar, retroceder, avançar e mover o scrubber com setas, Page Up/Down,
   Home e End.
7. No modo Foco, confirmar que as palavras rápidas não inundam a fala e que a
   ajuda indica o modo Fluxo. No Fluxo, ler o conteúdo contínuo, selecionar uma
   palavra e usar “Voltar pra posição atual”.
8. Abrir capítulos, navegar para um capítulo e confirmar o anúncio pontual da
   nova posição.
9. Ativar o Narrador, escolher voz e velocidade, reproduzir, pausar e buscar.
   Confirmar os estados de carregamento, erro recuperável e conclusão.
10. Abrir Atalhos, Estatísticas e Sistema; validar headings, listas, estados e
    mensagens degradadas. Alternar skins e tema sem perder o ponto de foco.
11. Executar todo o fluxo apenas com teclado/gestos da tecnologia assistiva e
    finalizar com logout.

## Registro e severidade

Para cada combinação, registre data, versões, skin/tema, fluxo, resultado,
passos de reprodução e evidência sem dados pessoais.

- **Crítico:** autenticação, importação, leitura, organização ou logout
  impossíveis; perda total de contexto ou armadilha sem saída.
- **Alto:** controle essencial sem nome/estado, foco imprevisível que impede o
  fluxo, conteúdo principal ausente ou anúncios contínuos inutilizáveis.
- **Médio:** experiência confusa, redundante ou trabalhosa, mas concluível.
- **Baixo:** inconsistência menor sem perda de informação ou operação.

O R9 só pode ser marcado como concluído com zero achado crítico/alto e com todas
as quatro famílias executadas. Achados médios/baixos precisam de correção ou
aceite explícito e rastreável antes do R14.
## R10 — visão, cor e mobilidade: matriz humana pendente

O gate automatizado cobre 20 combinações de estado/skin/emulação e mede 60
situações de reflow em 1280, 640 e 320 CSS px. Ele grava o relatório
`release-reports/r10-reflow-latest.json` e capturas sanitizadas de 320 px. Essa
evidência não substitui as verificações abaixo.

| Verificação | Plataforma/equipamento | Estado |
|---|---|---|
| Zoom real 100%, 200% e 400% | Edge/Firefox/Chrome em Windows e navegador móvel | Pendente |
| Alto contraste do sistema / `forced-colors` | Windows 11 | Pendente |
| Protanopia, deuteranopia, tritanopia e acromatopsia | Simulador confiável e inspeção humana | Pendente |
| Switch scanning | Windows ou Android com acionador configurado | Pendente |
| Voice Access / controle por voz | Windows 11 | Pendente |
| Rastreamento ocular, quando disponível | Equipamento compatível | Pendente |

### Roteiro complementar

1. Executar cada view, diálogo, skin e orientação em 100%, 200% e 400%; confirmar
   que não há conteúdo cortado, sobreposição de controles nem rolagem horizontal
   da página. A rolagem interna explícita das abas de prateleira é permitida.
2. Aplicar espaçamento de texto do usuário (linha 1,5, parágrafo 2×, letra
   0,12em e palavra 0,16em) e zoom de texto; confirmar leitura e formulários.
3. Ligar Alto Contraste do Windows e também inversão; confirmar que foco,
   seleção, erro, progresso e saúde continuam compreensíveis por texto, contorno
   ou ícone, não apenas por cor.
4. Revisar os quatro filtros de visão de cor no login, biblioteca, documento
   abandonado, progresso, erros, TTS e Sistema. Registrar screenshot e qualquer
   ambiguidade humana.
5. Executar criação, importação, busca, prateleiras, leitura Foco/Fluxo/TTS,
   scrubber e logout somente por Tab/Shift+Tab, Enter, Espaço e setas; repetir
   com switch scanning e Voice Access. O scrubber deve funcionar por setas,
   Page Up/Down, Home e End sem arrasto.
6. Quando houver rastreamento ocular, repetir o fluxo essencial, verificar alvos
   de 48 px e registrar modelo/configuração do equipamento.

O R10 só pode ser marcado como concluído com essas matrizes sem perda funcional
e com zero achado crítico/alto. A automação atual protege regressões, mas não
substitui esses aceites humanos.

## R11 — neurodiversidade, dislexia e controle cognitivo: matriz humana pendente

A automação protege os controles, a fonte local licenciada, a marca Biônica
oculta da árvore acessível e as combinações renderizadas nas duas skins. Ela não
substitui pessoas lendo por períodos prolongados. Execute este roteiro em cada
skin, tema e com leitor de tela quando disponível:

1. No Fluxo, ligar/desligar Leitura Biônica em documento curto e em um documento
   patológico; confirmar que a palavra é ouvida uma vez, sem soletração por
   partes, e que não há travamento ao rolar.
2. Selecionar OpenDyslexic e depois Fonte do sistema; alterar coluna, linha,
   letras e palavras; confirmar reversão imediata, reflow e persistência após
   logout/login sem alegar benefício clínico.
3. Ligar Guia, Miras ORP e Baixa estimulação; confirmar contraste, foco, texto e
   estado compreensíveis em zoom real, `forced-colors` e reduced motion.
4. No Foco e Fluxo, entrar e sair do Zen apenas por teclado. Pausa/reprodução e
   saída devem continuar alcançáveis; título, progresso, contadores e ações
   secundárias devem permanecer ocultos enquanto Zen estiver ativo.
5. Com Narrador em 0,5x, 1x e 4x, pausar, buscar, trocar Foco/Fluxo e desligar
   o acompanhamento do Fluxo. Confirmar que não há autoplay, rolagem imposta,
   perda de posição ou diferença entre áudio e destaque.
6. Registrar duração, navegador, skin, configurações, tecnologia assistiva,
   fadiga/confusão observada e qualquer achado sem dados pessoais.

O R11 só é aceito após não haver barreira crítica/alta nesse roteiro; preferências
cognitivas continuam opcionais e não são apresentadas como tratamento médico.