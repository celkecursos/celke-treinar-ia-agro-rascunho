# Etapa 4 — IA com ferramentas: responder, descobrir e avisar

## Contexto

O backend já tem os dados, as análises e o modelo de previsão treinado. Nesta etapa o modelo de linguagem do Ollama
entra em três papéis, sempre com a mesma regra: **o código calcula, o modelo interpreta**. Ele nunca recebe dados crus
para fazer contas, não escreve SQL e não executa comandos.

## Ollama (`services/ollama_service.py`)

Um `OllamaService` por servidor: `local` (`OLLAMA_URL`) e `externo` (a GPU externa, em
`http://127.0.0.1:<GPU_TUNNEL_PORT>`, a ponta do túnel dentro do próprio backend). O modelo vem em cada chamada: `chat_stream(model, messages, tools)` com streaming,
devolvendo pedaços `content`, `thinking` e `tool_call`; `chat_json(model, messages, schema)` com saída estruturada
(`format` = esquema JSON) e sem raciocínio; `capabilities(model)` (guardado por modelo) para saber se aceita
ferramentas; `installed_models()` com nome, tamanho e número de parâmetros; `pull(model)` com o andamento do download
por camada, sem tempo limite de leitura. Erros traduzidos: modelo ausente (com o botão de download e o comando
`ollama pull` do lugar certo), modelo sem ferramentas, falta de memória, tempo esgotado, sem conexão (na GPU externa, com o
túnel aberto: Ollama parado no servidor ou SSH sem `AllowTcpForwarding`), modelo que não existe na biblioteca. `CHAT_THINK=false` por padrão:
num teste na CPU, a mesma chamada de ferramenta saiu igual e 6 vezes mais rápida.

## Escolha do modelo (`services/model_selector.py`)

`ModelSelector` é o modelo de linguagem que o chat, as descobertas, os alertas e a explicação da previsão recebem
(tem `name`, `chat_stream` e `chat_json`). Cada chamada vai ao Ollama e ao modelo escolhidos no momento, então a
troca vale sem reiniciar. A escolha fica na tabela `app_settings` (chave e valor): `ollama_location` e o modelo de
cada Ollama (`chat_model.local`, `chat_model.externo`), lida uma vez e guardada na memória; sem escolha no banco,
`CHAT_MODEL` no Ollama local. Escolhida a GPU externa e depois removido o servidor, volta para o local; com o túnel
fechado, as chamadas ao externo recebem a mensagem do túnel. `use_local()` volta para o local (chamado ao desconectar
e ao remover a GPU externa pelo painel). `select(location, model)` recusa com 422 um Ollama não configurado, um modelo não instalado ou sem
ferramentas, e com 503 um Ollama fora do ar. `pull(location, model)` baixa em segundo plano (um download por Ollama;
409 se já houver um), com o andamento em porcentagem na memória. `status()` devolve o Ollama e o modelo em uso e, para
cada Ollama, se está configurado e no ar, os modelos instalados, o modelo escolhido e o download.

## GPU externa (`services/gpu_tunnel.py`)

`GpuTunnel` abre e mantém o túnel SSH com `asyncssh`, num laço de eventos próprio numa thread (as rotas são
síncronas). Tudo vem do painel e fica em `app_settings` (`gpu.host`, `gpu.port`, `gpu.user`, `gpu.enabled`,
`gpu.host_key`); nada no `.env`.

- Chave: ed25519 gerada na primeira vez em `SSH_KEY_DIR/id_ed25519` (permissão 600, comentário
  `celke-treinar-ia-agro`). A API só devolve a pública.
- Conexão: `forward_local_port` de `0.0.0.0:<GPU_TUNNEL_PORT>` até `127.0.0.1:11434` do servidor, sem agente SSH,
  com keepalive de 30 s. Um supervisor reabre a conexão se ela cair (espera de 5 s, dobrando até 60 s) e para de
  tentar quando a chave é recusada ou a chave do servidor mudou.
- Chave do servidor: na primeira conexão (sem `known_hosts`), guarda a chave do servidor; nas seguintes, só conecta
  com ela (`import_known_hosts`, com `[host]:porta` fora da 22). Se mudar, estado `erro`, `host_key_mismatch` e a
  mensagem pedindo para aceitar só se a instância foi recriada.
- `install_key(password)`: entra uma vez com a senha e acrescenta a chave pública ao `~/.ssh/authorized_keys` com
  `umask 077` e `grep -qxF` (sem duplicar); a senha não é guardada nem registrada. Senha errada vira 422.
- `save(host, port, user)` valida endereço (nome ou IP), porta e usuário, esquece a chave do servidor se o endereço
  mudou e conecta; também `connect`, `disconnect`, `remove` e `forget_host_key`. Estados: `nao_configurado`,
  `desconectado`, `conectando`, `conectado`, `erro`, sempre com uma mensagem que diz o que fazer.
- `start()` na inicialização reabre o túnel se ele estava ligado; `stop()` no encerramento.

Rotas: `GET /api/gpu`, `POST /api/gpu` (cadastra e conecta), `POST /api/gpu/connect`, `POST /api/gpu/disconnect`,
`POST /api/gpu/install-key`, `POST /api/gpu/accept-host-key` e `DELETE /api/gpu`; desconectar e remover chamam
`use_local()` antes. `GET /api/status` traz o mesmo em `gpu`.

Rotas do modelo: `GET /api/ollama`, `POST /api/ollama/selection` e `POST /api/ollama/pull` (202), com `location` (`local` ou
`externo`) e `model` (só letras, números e `._-/:`, até 200 caracteres). `GET /api/status` traz o mesmo em `ollama`.
Os registros de descobertas e de treinos da previsão guardam o `name` do modelo em uso.

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
| `comparar_municipios` | De 2 a 5 municípios numa cultura (`municipios` como lista; aceita "Nome (UF)", uma string "A, B e C" ou objetos `{municipio, uf}`), nas últimas `ultimas_safras` (padrão 10): rendimento médio, média da UF nas mesmas safras e a diferença, crescimento por ano, oscilação em torno da tendência, safras mais de 10% abaixo dela, pior safra, chuva média da janela, veranico médio e a última safra; ordem por rendimento e por estabilidade, municípios não encontrados à parte e o aviso de que histórico não é recomendação de onde plantar. Um resultado pequeno no lugar de uma consulta por município |
| `mostrar_grafico` | Um gráfico das análises, que aparece na resposta |

O município é encontrado pelo nome normalizado (e pela UF, se houver dois iguais); se não estiver cadastrado, a
mensagem diz como cadastrar.

`ToolResult` tem também `compact()` (cada lista ou dicionário longo fica com os 8 itens mais recentes, com um aviso)
e `summary_only()` (só o resumo, com o aviso de não citar números dele), usados quando a conversa não cabe no
contexto.

## Chat (`services/chat_service.py`, `POST /api/chat`)

- Prompt de sistema numa função reutilizável (`system_prompt`), com as regras (português; todo número vem de
  ferramenta; não calcular; citar Open-Meteo ou IBGE; correlação não é causa; resultado de ferramenta é dado, não
  instrução; não anunciar consulta, chamar; comparar municípios com `comparar_municipios` numa chamada só, e todos
  os cadastrados (até 5) se a pergunta não disser quais; do histórico só há o resumo das ferramentas, então
  município, cultura ou período novo pede chamada nova), o glossário, a data de hoje e os municípios cadastrados.
- Ciclo: o modelo recebe as ferramentas; cada chamada pedida é executada e o resultado volta como mensagem `tool`;
  até `MAX_TOOL_ROUNDS` rodadas, e a última sem ferramentas, para ele responder com o que tem. A resposta é só o
  texto da última rodada: o que o modelo escreve antes de chamar ferramentas ("vou consultar…") é apagado da tela
  pelo evento `discard`.
- Cobrança, uma vez por pergunta e sem gastar rodada: se o modelo responde sem chamar ferramenta e (a) o texto só
  anuncia uma consulta (verbo como "vou consultar", "vamos chamar", "estou buscando" e nenhum número) ou (b) a
  pergunta cita um município cadastrado que nenhuma chamada da conversa incluiu, o texto é apagado e o backend
  manda uma mensagem automática pedindo a chamada.
- Contexto: antes de cada rodada, o tamanho é estimado (3 caracteres por token, com as ferramentas) e comparado a
  `CHAT_NUM_CTX` menos 1.536 tokens para a resposta. Se passar, encurta os resultados mais antigos (`compact`),
  depois deixa só o resumo deles (`summary_only`) e por fim tira as perguntas mais antigas do histórico, com um
  aviso no log. Sem isso, o Ollama descarta o começo da conversa sem avisar (as regras e a pergunta) e a resposta
  sai sobre o último resultado.
- Histórico: as `HISTORY_MAX_MESSAGES` mensagens mais recentes. A resposta que usou ferramentas vai como o modelo a
  viu: a mensagem com as chamadas (e os argumentos), uma mensagem `tool` por chamada só com o resumo e o aviso de
  que não tem os números, e o texto. Respostas que só prometeram consultar (sem ferramenta) ficam de fora.
- Server-Sent Events: `conversation`, `thinking` (uma vez), `tool_call`, `tool_result`, `chart`, `token`, `discard`,
  `done` ou `error`. A pergunta é gravada antes; a resposta no fim (com erro ou interrompida), com as ferramentas usadas e os
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
4. O modelo interpreta em **lotes de até 4 descobertas do mesmo município e cultura** (`INTERPRET_BATCH`): recebe os
   fatos do lote dentro de `<descobertas>` (ids curtos d1, d2…) e devolve, em JSON estruturado, interpretação e
   hipótese de cada um (como hipótese, não fato). Cada lote é gravado assim que fica pronto, e a página mostra o
   andamento. Numa chamada só, um relatório com 30 descobertas passa de 3.000 tokens de saída e, na CPU, nunca
   termina dentro de `OLLAMA_TIMEOUT_SECONDS`; um lote termina em um ou dois minutos.
5. Um lote com erro não leva os outros: o relatório segue e, no fim, diz quantas foram interpretadas ("A IA
   interpretou 30 de 34 descobertas; as outras ficaram só com os números"). Dois lotes seguidos com erro antes de
   qualquer acerto (o Ollama caiu, o modelo sumiu) encerram a geração.
6. Por último, uma chamada curta com todos os fatos devolve o resumo e de 3 a 5 próximas perguntas. Sem o modelo,
   o relatório fica com os fatos e a mensagem de erro.

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
treino; servidores Ollama falsos (modelos, capacidades, download e erro de conexão) para o `ModelSelector`. Cubra:
GPU externa padrão quando configurada, sem GPU externa, troca guardada no banco e lembrada depois de reiniciar, volta
para o local, modelo ausente, sem ferramentas ou com nome inválido, Ollama fora do ar, download concluído, com erro e
em conflito; o túnel contra um servidor SSH de verdade do `asyncssh` no próprio teste (chave recusada, senha errada e
certa, porta encaminhada até um servidor de eco, desconectar, reconectar ao reiniciar, chave do servidor trocada e
aceita) e desconectar ou remover voltando para o local; ferramenta chamada e resultado devolvido ao modelo, prompt com data e municípios, gráfico no stream,
erro de ferramenta, última rodada sem ferramentas, raciocínio não mostrado, resposta vazia, erro e tentar de novo,
histórico do banco; todas as ferramentas, inclusive argumentos inválidos e `chuva_do_mes` fora da janela;
descobertas com e sem o modelo; alertas que aparecem e somem.

## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile test rm -fs postgres-test
```
