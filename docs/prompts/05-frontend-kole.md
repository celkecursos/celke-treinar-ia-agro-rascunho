# Etapa 5 — Frontend React com o Kole

## Contexto

O backend responde em `/api` (etapas 2 a 4). Nesta etapa você cria o frontend em `frontend/`: React 19 com
TypeScript e Vite, React Router e o layout da Celke, o pacote **`@celke/kole-react`**, que traz os gráficos
(`GraficoLinha`, `GraficoBarras`, `GraficoCombinado`, `GraficoDispersao`, `MapaCalor`, `Indicador` com `tendencia`). O
nginx serve o build e repassa `/api` ao backend, então o navegador só fala com uma origem.

## Antes de escrever código

1. Instale e leia a biblioteca: depois do `npm install`, o `node_modules/@celke/kole-react/README.md` e os tipos em
   `node_modules/@celke/kole-react/dist`. Use só componentes, props e exports que existem. As props são em português
   (`rotulo`, `valor`, `aoMudar`) e ficam como estão.
2. Os gráficos estão na versão 0.4.0. Enquanto ela não estiver no npm, instale direto do GitHub:
   `"@celke/kole-react": "git+https://github.com/celkecursos/kole-react.git#v0.4.0"` (o `prepare` do pacote gera o
   `dist`). O `Dockerfile` instala o `git` no estágio de build por causa disso.

## Dependências (`frontend/package.json`)

```json
"dependencies": {
  "@celke/kole-react": "git+https://github.com/celkecursos/kole-react.git#v0.4.0",
  "lucide-react": "^1.60.0",
  "react": "^19.3.1",
  "react-dom": "^19.3.1",
  "react-router": "^8.5.1"
},
"devDependencies": {
  "@types/react": "^19.3.0",
  "@types/react-dom": "^19.3.0",
  "@vitejs/plugin-react": "^6.1.2",
  "typescript": "~6.0.3",
  "vite": "^8.3.5",
  "vitest": "^5.0.5"
}
```

Scripts: `dev`, `build` (`tsc --noEmit && vite build`), `typecheck`, `test` (`vitest run`). `Dockerfile` em
estágios a partir de `node:24-alpine` (com `git`): `build` (`npm ci`), `test` (`npm run typecheck && npm test`),
`bundle` e `runtime` (`nginx:1.30-alpine` com `nginx.conf`: `/api/` para `http://backend:8000` sem buffer e com
`proxy_read_timeout 900s`, `/assets/` com cache longo, o resto com `try_files $uri /index.html`, cabeçalhos de
segurança repetidos em cada `location`). Gere o `package-lock.json` no Docker (com `git` instalado na imagem).

## Organização

- `main.tsx`: `ProvedorUi`, estilos do Kole e `registrarIcones` com os ícones do `lucide-react` que não vêm
  registrados (activity, bell, bot, brain, calendar-clock, chart-scatter, cloud-rain, cpu, database, history,
  lightbulb, plus, sparkles, sprout, trash-2, wrench).
- `layouts/AppLayout.tsx`: `Estrutura` com marca curta ("Celke Agro", subtítulo "Treinar IA") e o menu: Análises;
  **Inteligência**: Previsão (treino), Chat, Descobertas, Alertas; **Dados**: Municípios, Status e coletas. Rodapé com
  as fontes (Open-Meteo CC BY 4.0 e IBGE).
- `services/api.ts`: toda chamada à API, com `ApiError` e a mensagem do backend; `streamChat` com `fetch` e
  `AbortSignal`. `services/sse.ts`: leitura do streaming em blocos, com os eventos `conversation`, `thinking`,
  `tool_call`, `tool_result`, `chart`, `token`, `done` e `error`.
- `components/chartProps.ts` e `components/ChartView.tsx`: a especificação do backend vira o componente do Kole pelo
  `tipo`, trocando snake_case por camelCase. Nenhuma conta no frontend.
- `hooks/usePolling.ts`: carrega e repete enquanto ativo.

## Páginas

| Página | Conteúdo |
|---|---|
| **Análises** (`/`) | Município (`CampoSelect`) e cultura (`Escolha` soja/milho) na URL; alertas do município; indicadores com minigráfico; os gráficos em `Card` (o primeiro na largura toda); estimativa da LSPA em `Tabela`; notas de método em card recolhível. Sem município: `Vazio` com o botão de cadastrar |
| **Previsão (treino)** (`/previsao`) | O que o modelo aprendeu: safras de treino, modelos testados, erro do modelo × erro da tendência, variáveis com os coeficientes (`Chip`), equação treinada, explicação da IA; gráfico real × previsto; um card por safra prevista (previsto com faixa e variação × tendência, tendência, estimativa do IBGE, chuva); gráfico dos cenários; histórico de treinos; botão **Treinar de novo**, atualizando sozinho enquanto treina |
| **Chat** (`/chat`) | `Conversa`, `Mensagem` e `CampoMensagem`, como num chat comum; exemplos de pergunta no vazio; a pergunta pode chegar por `?pergunta=`; enquanto gera, "Consultando: Chuva no período…"; gráficos dentro da resposta; ferramentas usadas como `Referencias` (nome amigável, fonte, resumo e argumentos); conversas salvas em `Dialogo` lateral, excluir com `useConfirmacao`, tentar de novo |
| **Descobertas** (`/descobertas`) | Resumo da IA, modelo e quantas relações foram testadas; próximas perguntas com botão para perguntar no chat; cada descoberta com o fato calculado, r/q/n, interpretação, hipótese e o gráfico; aviso quando a IA não conseguiu interpretar; botão **Gerar de novo** |
| **Alertas** (`/alertas`) | Ativos ou todos; cada alerta com a mensagem, a explicação da IA, chuva × média, gráfico da chuva acumulada e a tabela das safras parecidas |
| **Municípios** (`/municipios`) | Cadastro com `CampoUf` e `CampoCidade` (lista do IBGE pelo backend); tabela com situação e a mensagem do passo atual, período da chuva, último ano da produção, ações (ver análises, excluir); botão **Coletar chuva agora**; atualização a cada 3 s |
| **Status e coletas** (`/status`) | Um card por fonte com o último dado, o agendamento, a última coleta e o botão **Buscar agora** (desabilitado enquanto coleta); registro das coletas com quando, fonte, origem, situação, registros e mensagem; serviços (backend, Ollama, modelo com ferramentas, PostgreSQL, agendador) |

Estilos próprios só em `src/styles.css`, com as variáveis do tema do Kole (`--surface`, `--t2`, `--t3`, `--border`,
`--pri`…); nada de cor fixa. O chat ocupa exatamente a área de conteúdo e só a conversa rola.

## Testes

Vitest: `parseSseBlock` com os eventos de ferramenta e gráfico, `readSse` com blocos partidos, `chartProps`.

## Verificação

```bash
docker compose --profile test run --rm --build frontend-tests
docker compose up -d --build
docker compose ps                                     # todos healthy; só o frontend com porta
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8091/previsao   # 200
```

Abra http://localhost:8091 nos temas claro e escuro e confira os gráficos.
