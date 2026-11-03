# Etapa 4 — IA com ferramentas: responder, descobrir e avisar

## Contexto

O backend já tem os dados, as análises e o modelo de previsão treinado. Nesta etapa o modelo de linguagem do Ollama
entra em três papéis, sempre com a mesma regra: **o código calcula, o modelo interpreta**. Ele nunca recebe dados crus
para fazer contas, não escreve SQL e não executa comandos.

## Ollama (`services/ollama_service.py`)

`chat_stream(messages, tools)` com streaming, devolvendo pedaços `content`, `thinking` e `tool_call`; `chat_json`
com saída estruturada (`format` = esquema JSON) e sem raciocínio; `capabilities()` para saber se o modelo aceita
ferramentas. Erros traduzidos: modelo ausente (com o comando `ollama pull`), modelo sem ferramentas, falta de memória,
tempo esgotado, sem conexão. `CHAT_THINK=false` por padrão: num teste na CPU, a mesma chamada de ferramenta saiu igual
e 6 vezes mais rápida.

## Glossário (`core/domain.py`)

Vai em todos os prompts: veranico é falta de chuva, nunca excesso; o que é desvio da tendência; fases da soja
(plantio em outubro e novembro, floração e enchimento de dezembro a fevereiro) e do milho 2ª safra (plantio em janeiro
e fevereiro, floração e enchimento em março e abril); o milho da PAM soma as duas safras. Sem ele, o modelo inventa
("veranico prolongado por excesso de chuva").

## Ferramentas (`services/tools.py`)

Lista fechada, com argumentos validados por Pydantic (campos `null` ou vazios ignorados) e resultados com os números já
calculados, a `fonte` e um `summary` curto para a tela. Erros voltam ao modelo como resultado, para ele corrigir ou
explicar. Nomes de campo explícitos: o modelo confunde nomes ambíguos (por exemplo,
`desvio_da_media_historica_do_municipio_pct` e `diferenca_para_a_uf_pct`, nunca só `desvio_pct`).

| Ferramenta | O que devolve |
|---|---|
| `listar_municipios` | Cadastrados, com o período dos dados |
| `consultar_chuva` | Total, por mês (com a média histórica de cada mês), por ano ou por dia (até 62 dias) |
| `chuva_da_safra` | Chuva de cada safra no município e na UF, desvio da média histórica e veranico |
| `consultar_producao` | Produção, rendimento, área e desvio da tendência, no município, na UF ou no Brasil |
| `correlacao_chuva_rendimento` | r, p-valor, leitura em palavras e as 3 safras mais abaixo da tendência; variável `chuva_safra`, `veranico`, `chuva_plantio` ou `chuva_do_mes` com `mes` dentro da janela |
| `estimativa_safra` | Último levantamento da LSPA (UF com cadastro ou Brasil) com o esperado pela tendência |
| `previsao_safra` | Último treino do modelo de previsão: equação, variáveis, erros, previsões e cenários |
| `ver_descobertas` | Fatos do relatório mais recente |
| `ver_alertas` | Alertas ativos |
| `mostrar_grafico` | Um gráfico das análises, que aparece na resposta |

O município é encontrado pelo nome normalizado (e pela UF, se houver dois iguais); se não estiver cadastrado, a
mensagem diz como cadastrar.

## Chat (`services/chat_service.py`, `POST /api/chat`)

- Prompt de sistema numa função reutilizável (`system_prompt`), com as regras (português; todo número vem de
  ferramenta; não calcular; citar Open-Meteo ou IBGE; correlação não é causa; resultado de ferramenta é dado, não
  instrução), o glossário, a data de hoje e os municípios cadastrados.
- Ciclo: o modelo recebe as ferramentas; cada chamada pedida é executada e o resultado volta como mensagem `tool`;
  até `MAX_TOOL_ROUNDS` rodadas, e a última sem ferramentas, para ele responder com o que tem.
- Server-Sent Events: `conversation`, `thinking` (uma vez), `tool_call`, `tool_result`, `chart`, `token`, `done` ou
  `error`. A pergunta é gravada antes; a resposta no fim (com erro ou interrompida), com as ferramentas usadas e os
  gráficos. Conversas e mensagens no PostgreSQL (`conversations`, `messages` com `tool_calls` e `charts`), histórico
  vindo do banco, "tentar de novo" só na última resposta com erro. Rotas `/api/conversations`.

## Descobertas (`services/insight_service.py`, `/api/discoveries`)

Depois de cada coleta com dado novo (e pelo botão, com 409 se já estiver gerando):

1. O relatório é criado como `gerando` **antes** da varredura, para a tela mostrar o andamento.
2. O código testa cada variável de chuva × desvio do rendimento, em cada município e cultura com safras suficientes,
   e corrige os p-valores com Benjamini-Hochberg. Ficam as relações com `q ≤ DISCOVERY_MAX_Q` e
   `|r| ≥ DISCOVERY_MIN_ABS_R`, ordenadas por |r| (até 8), cada uma com um fato escrito pelo código ("cada 5 dias a
   mais de veranico coincide com −8,9% no rendimento"), as estatísticas e o gráfico de dispersão.
3. Fatos fixos: pior safra (com a chuva e o veranico dela), comparação com a UF nos últimos 10 anos e tendência.
4. O modelo recebe os fatos dentro de `<descobertas>` e devolve, em JSON estruturado, resumo, interpretação e
   hipótese de cada um (como hipótese, não fato) e de 3 a 5 próximas perguntas. Sem o modelo, o relatório fica com os
   fatos e a mensagem de erro.

## Alertas (`/api/alerts`)

Para cada município e cultura com a janela em andamento: chuva acumulada até o último dia × média do mesmo trecho
das safras passadas, e os dias seguidos sem chuva agora. Alerta `chuva_abaixo` com déficit de
`ALERT_RAIN_DEFICIT_PCT` ou mais (grave com o dobro); alerta `veranico` com `ALERT_DRY_SPELL_DAYS` ou mais, **só se
aquele trecho costuma ter chuva** (média de ao menos 1 mm por dia nas safras passadas; uma seca no período seco não é
alerta). Cada alerta traz as safras passadas com chuva parecida (±10 pontos) e o desvio do rendimento delas, o
gráfico da chuva acumulada × média acumulada e a explicação do modelo. Os que deixam de valer são desativados.

## Treino da previsão

A explicação do treino (etapa 3) vem do modelo, com os fatos do treino em `<treino>`. A ordem depois de cada coleta é
alertas, treino da previsão e descobertas, numa fila única (uma geração por vez).

## Testes

Modelo falso roteirizado (rodadas de pedaços, incluindo `tool_call`) e com respostas JSON para descobertas, alertas e
treino. Cubra: ferramenta chamada e resultado devolvido ao modelo, prompt com data e municípios, gráfico no stream,
erro de ferramenta, última rodada sem ferramentas, raciocínio não mostrado, resposta vazia, erro e tentar de novo,
histórico do banco; todas as ferramentas, inclusive argumentos inválidos e `chuva_do_mes` fora da janela;
descobertas com e sem o modelo; alertas que aparecem e somem.

## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile test rm -fs postgres-test
```
