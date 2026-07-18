# Matriz de avaliação assistiva — R9

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