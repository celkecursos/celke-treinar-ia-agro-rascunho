# Celke Treinar IA Agro

**Como treinar IA com dados do agro.** Uma IA local que coleta dados públicos de chuva (Open-Meteo) e de produção
de soja e milho (IBGE) e **treina dois modelos com eles**: um modelo de previsão do rendimento da safra, retreinado a
cada coleta, e um fine-tuning LoRA do modelo de linguagem, que aprende a consultar os dados. O modelo de linguagem
roda no seu computador (Ollama) e também responde perguntas, encontra relações e avisa quando a safra em andamento
foge do normal. Tudo roda no Docker: não é preciso instalar Python nem Node.js, e não há API paga.

## Índice

- [Como executar (quem baixou do GitHub)](#como-executar-quem-baixou-do-github)
- [Os dois treinamentos](#os-dois-treinamentos)
- [Fine-tuning do modelo de linguagem (GPU)](#fine-tuning-do-modelo-de-linguagem-gpu)
- [GPU externa (Hostinger e similares)](#gpu-externa-hostinger-e-similares)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Fontes de dados](#fontes-de-dados)
- [Método](#método)
- [Configuração](#configuração)
- [Testes](#testes)
- [Comandos úteis](#comandos-úteis)
- [Hardware e escolha do modelo](#hardware-e-escolha-do-modelo)
- [Problemas comuns](#problemas-comuns)
- [Segurança e privacidade](#segurança-e-privacidade)
- [Evolução do projeto](#evolução-do-projeto)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Prompts para recriar o projeto](#prompts-para-recriar-o-projeto)

## Como executar (quem baixou do GitHub)

### 1. O que você precisa

| O quê | Observação |
|---|---|
| Docker Desktop (Windows, macOS) ou Docker Engine com o plugin Compose (Linux) | No Windows, com WSL 2 |
| Git | Para baixar o projeto |
| Internet | Na primeira vez: imagens Docker, pacotes e o modelo (de 5 a 9 GB) |
| 16 GB de RAM | Com o modelo padrão `qwen3:8b` rodando na CPU. Com GPU NVIDIA, fica bem mais rápido |
| 20 GB livres em disco | Imagens, modelo e dados |

Não instale o Ollama, o Python nem o Node.js: tudo roda dentro do Docker.

### 2. Baixar e subir

```bash
git clone https://github.com/celkecursos/celke-treinar-ia-agro-rascunho.git celke-treinar-ia-agro
cd celke-treinar-ia-agro
```

Linux, macOS ou Git Bash no Windows:

```bash
./scripts/iniciar.sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1
```

O script cria o `.env` com uma senha aleatória para o banco, sobe os containers, espera o download do modelo e
termina com `Pronto! Abra http://localhost:8091`. **A primeira vez demora**: de alguns minutos a mais de uma hora,
conforme a internet, porque baixa o modelo de IA. Para acompanhar o download, em outro terminal:
`docker compose logs -f ollama-init`. Das próximas vezes, sobe em segundos.

Com GPU NVIDIA, antes de rodar o script, copie `.env.example` para `.env` e descomente a linha `COMPOSE_FILE` do
seu sistema. Com uma GPU de 12 GB, troque também `CHAT_MODEL=qwen3:14b` (veja
[Hardware e escolha do modelo](#hardware-e-escolha-do-modelo)).

### 3. Usar no navegador

1. Abra **http://localhost:8091** e confira em **Status e coletas** se o Ollama, o modelo e o banco estão verdes.
2. Em **Municípios**, escolha a UF e o município e clique em **Cadastrar**. O sistema baixa a chuva diária desde
   2000 e a produção de soja e milho do IBGE. Leva cerca de 1 minuto; a tabela mostra o andamento.
3. Em **Análises**, veja a chuva de cada safra cruzada com o rendimento, os indicadores e os gráficos.
4. Em **Chat**, pergunte. Exemplo: "A chuva de abril influencia o rendimento do milho em Rio Verde?". A IA escolhe
   as ferramentas, o sistema faz as contas, e a resposta mostra as ferramentas usadas como fontes.
5. Em **Previsão (treino)**, veja o modelo que o sistema treinou com as safras do município: as variáveis que ele
   escolheu, o erro medido e a previsão da próxima safra.
6. Em **Descobertas**, leia as relações que passaram no filtro estatístico, interpretadas pela IA. O relatório é
   gerado depois de cada coleta e também pelo botão **Gerar de novo**.
7. Em **Alertas**, acompanhe a safra em andamento: chuva bem abaixo da média ou muitos dias sem chuva.

A primeira resposta da IA demora mais, porque o modelo é carregado na memória. Na CPU, uma pergunta com
ferramentas leva cerca de 1 minuto com o `qwen3:8b`.

### 4. Parar, voltar e apagar

```bash
docker compose stop                 # para, sem perder nada
docker compose start                # volta
docker compose down -v              # apaga tudo: dados, conversas e o modelo baixado
```

## Os dois treinamentos

O projeto treina de verdade, com os dados que ele mesmo coleta, e mede se o treino funcionou.

| | 1. Previsão da safra | 2. Fine-tuning do modelo de linguagem |
|---|---|---|
| **O que aprende** | Como o rendimento (kg/ha) responde ao ano (tecnologia) e à chuva | A escolher a ferramenta certa e preencher os argumentos (ex.: "safra 2023/24" → `ano=2024`, "safrinha" → milho) |
| **Com quais dados** | As safras do município: chuva (Open-Meteo) e rendimento (IBGE) | Perguntas geradas dos municípios cadastrados e as perguntas reais do chat que deram certo |
| **Como é treinado** | Regressão por mínimos quadrados; o sistema testa a tendência sozinha e as combinações de até 2 variáveis de chuva | LoRA em 4 bits (Unsloth) sobre o Qwen3, exportado em GGUF para o Ollama |
| **Como é medido** | Cada safra é prevista por um modelo treinado sem ela; o erro é comparado ao da tendência sozinha | Acerto em perguntas com redações que não estão no treino, antes e depois |
| **Quando treina** | Sozinho depois de cada coleta, e pelo botão **Treinar de novo** | Quando você roda o treino (etapa opcional, precisa de GPU NVIDIA) |
| **Onde aparece** | Página **Previsão (treino)** e a ferramenta `previsao_safra` do chat | `CHAT_MODEL=celke-agro` no `.env` |

Exemplo real com Rio Verde (GO): o modelo do milho escolheu o maior veranico e a chuva de janeiro e errou, em média,
486 kg/ha (9%) safra a safra, contra 688 kg/ha (13,5%) da tendência sozinha: a chuva reduziu o erro em 29%. Na
soja, a chuva quase não melhorou a previsão (7%), e a tela diz isso.

**O que não é treinado:** os números de chuva e produção não vão para dentro do modelo de linguagem. Eles mudam todo
dia, ficam no PostgreSQL e chegam por ferramentas: um dado novo já vale na próxima pergunta. **As contas ficam no
código** (somas, médias, tendência, correlação, p-valor, regressão): num teste, o `qwen3:8b` errou uma média simples.

**Por que não há modelo de embeddings:** embeddings servem para busca por semelhança de texto (RAG), como a busca nos
trechos de PDFs do Celke IA Local. Aqui nenhum dos treinamentos precisa deles: a previsão é uma regressão sobre
números, o LoRA treina os pesos do próprio Qwen3 com texto, e o chat consulta as tabelas por ferramentas. Por isso a
página de Status não mostra modelo de embeddings: um modelo a mais só gastaria download e memória.

Além de prever, a IA tem três papéis com os dados:

| Papel | Onde | O que faz |
|---|---|---|
| **Responder** | Chat | Escolhe as ferramentas e os argumentos, recebe os números calculados e explica |
| **Descobrir** | Descobertas | O código testa combinações de chuva × rendimento e filtra pela estatística; a IA interpreta, levanta hipóteses e sugere perguntas |
| **Avisar** | Alertas | O código compara a safra em andamento com as passadas; a IA explica o que safras parecidas tiveram |

## Fine-tuning do modelo de linguagem (GPU)

Etapa opcional, que precisa de GPU NVIDIA (testada para uma RTX 3060 de 12 GB) e de pelo menos um município
cadastrado. No Windows, basta o Docker Desktop com WSL 2 e o driver NVIDIA; no Linux, o NVIDIA Container Toolkit.

```bash
# 1. Gera o dataset: finetuning/data/treino.jsonl e avaliacao.jsonl
docker compose --profile finetune run --rm --build finetune-tools exportar

# 2. Mede o acerto do modelo atual ("antes"), com perguntas que não estão no treino
docker compose --profile finetune run --rm finetune-tools avaliar --modelo qwen3:8b

# 3. Treina o LoRA na GPU e exporta o modelo inteiro em GGUF (baixa o modelo base na primeira vez)
docker compose --profile finetune run --rm --build finetune-train

# 4. Cria o modelo no Ollama, com o mesmo template de ferramentas do modelo base
docker compose exec ollama sh /finetuning/criar_modelo.sh qwen3:8b celke-agro

# 5. Mede de novo ("depois")
docker compose --profile finetune run --rm finetune-tools avaliar --modelo celke-agro
```

Para usar o modelo treinado no chat, coloque `CHAT_MODEL=celke-agro` no `.env` e rode o script de inicialização de
novo. Os relatórios da avaliação ficam em `finetuning/data/avaliacao-<modelo>.json`, com o acerto por tipo de pergunta
e os erros; as métricas do treino (perda inicial e final, tempo) em `finetuning/output/treino.json`.

Medição real do "antes", com Rio Verde (GO) cadastrado: o `qwen3:8b` sem treino escolheu a ferramenta certa em
94,3% das 35 perguntas novas e acertou ferramenta e argumentos em 88,6% (8,7 s por pergunta na CPU). Os erros são
exatamente o que o fine-tuning ensina:

| Pergunta | O modelo base fez | O certo |
|---|---|---|
| "Quanta chuva teve a safra 2006/07 de soja?" | `ano_inicio=2006, ano_fim=2007` | `ano=2007`: a safra é registrada no ano da colheita |
| "Gráfico de chuva por mês e ano" | Consultou a chuva | `mostrar_grafico` com o mapa de calor |
| "Efeito da seca no meio da safra no milho" | Chuva da safra | Correlação com o veranico |

O que esperar: o treino ensina comportamento, não números. O ganho é maior em modelos menores: com GPU de 8 GB, use
`FINETUNE_BASE_MODEL=unsloth/Qwen3-4B` e `qwen3:4b` como base no passo 4, e compare com o `qwen3:8b` sem treino.

## GPU externa (Hostinger e similares)

Sem GPU boa no computador, dá para alugar uma por hora, por exemplo uma
[instância de GPU da Hostinger](https://www.hostinger.com/br/gpu-hosting) (RTX 4090 com 24 GB a partir de R$ 2,31/h,
L40S com 48 GB a partir de R$ 5,27/h, com acesso root por SSH e o app Ollama pronto). Qualquer servidor Linux com GPU
NVIDIA, SSH e o Ollama serve. Há dois usos, independentes:

| Uso | O que roda no servidor | O que continua no seu computador |
|---|---|---|
| **Modelo do chat** | Ollama com o `CHAT_MODEL` (ex.: `qwen3:14b`, que não roda bem na CPU) | Frontend, backend, banco, coletas e o treino da previsão |
| **Fine-tuning** | O treino LoRA (de 20 a 60 minutos) | Tudo; o modelo treinado volta para `finetuning/output/` |

**Segurança:** o backend fala com o Ollama do servidor por um **túnel SSH** aberto pelo próprio Compose (serviço
`gpu-tunnel`, dentro da rede do Docker). A porta do Ollama não precisa ficar aberta na internet; se o painel do
provedor oferecer firewall, deixe aberta só a porta SSH. Use chave SSH, não senha.

**Custo:** a cobrança corre enquanto a instância existe. Desligue (ou apague) no painel quando terminar; apagar perde
os arquivos que não estiverem no armazenamento persistente.

### Modelo do chat na GPU externa

1. No painel, crie a instância com o app Ollama e cadastre a sua chave SSH pública (`~/.ssh/id_ed25519.pub`; sem
   chave, crie com `ssh-keygen -t ed25519`).
2. Baixe o modelo no servidor: `ssh root@<ip> ollama pull qwen3:14b`.
3. No `.env`:
   ```dotenv
   COMPOSE_FILE=compose.yaml;compose.externo.yaml   # no Linux e no macOS, separe com ":"
   GPU_SSH=root@<ip>
   GPU_SSH_KEY=~/.ssh/id_ed25519
   CHAT_MODEL=qwen3:14b
   ```
4. Rode o script de inicialização. O Ollama local não sobe; a página **Status e coletas** mostra "Ollama (GPU
   externa, pelo túnel SSH)". Se aparecer desconectado: `docker compose logs gpu-tunnel`.

Para voltar ao modelo local, tire as linhas do `.env` e rode o script de novo.

### Fine-tuning na GPU externa

Com o dataset gerado (`docker compose --profile finetune run --rm finetune-tools exportar`), na raiz do projeto
(Linux, macOS ou **Git Bash** no Windows):

```bash
./finetuning/treinar_remoto.sh root@<ip>
```

O script confere a GPU do servidor, envia o dataset e o `treinar.py`, instala as dependências fixas num ambiente
Python isolado (a primeira vez baixa cerca de 10 GB), treina e traz `celke-agro.gguf` e `treino.json` para
`finetuning/output/`. Depois, crie o modelo e meça o "depois" como no passo 4 e 5 de
[Fine-tuning](#fine-tuning-do-modelo-de-linguagem-gpu). Com o chat também na GPU externa, rode com
`CRIAR_NO_SERVIDOR=1` para criar o `celke-agro` direto no Ollama do servidor e use `CHAT_MODEL=celke-agro`.

Uma RTX 4090 (24 GB) treina o 8B com folga; com 48 GB (L40S) dá para treinar o `unsloth/Qwen3-14B`
(`FINETUNE_BASE_MODEL`), usando `qwen3:14b` como base no `criar_modelo.sh`.

## Funcionalidades

- **Municípios:** cadastro por UF e município (lista do IBGE). No cadastro, o sistema busca as coordenadas, baixa a
  chuva diária desde `HISTORY_START_YEAR`, escolhe os municípios que mais plantam soja na UF (referências da chuva
  média da UF) e baixa a produção do município, da UF e do Brasil. Exclusão com confirmação.
- **Coletas:** chuva automática todo dia (só os dias que faltam), produção (PAM) e estimativa da safra (LSPA)
  automáticas uma vez por mês. Cada fonte tem o botão **Buscar agora**. Uma coleta por vez em cada fonte; um
  segundo clique enquanto coleta é recusado. Sem dado novo, a coleta diz "Já está atualizado". Registro de cada
  coleta (quando, origem agendada/botão/cadastro, registros, mensagem) e data do último dado de cada fonte.
- **Análises:** por município e cultura (soja ou milho): chuva da safra, chuva média da UF, maior veranico,
  rendimento do município, da UF e do Brasil, tendência, desvio da tendência e correlação com p-valor. Gráficos do
  Kole: combinado (chuva × rendimento, dois eixos), dispersão com regressão, barras divergentes (desvio), linhas
  (rendimento comparado, chuva mensal), mapa de calor (ano × mês) e ranking das referências. Estimativa da safra
  em andamento (LSPA) comparada ao rendimento esperado pela tendência.
- **Chat:** 10 ferramentas (municípios, chuva no período, chuva das safras, produção, correlação, estimativa,
  previsão do modelo treinado, descobertas, alertas e gráfico). Resposta em streaming; as ferramentas usadas aparecem como fontes e os gráficos
  aparecem dentro da resposta. Conversas salvas no PostgreSQL, com histórico, tentar de novo e exclusão.
- **Descobertas:** varredura de chuva da safra, veranico e chuva de cada mês da janela × desvio do rendimento, com
  correção para muitos testes (Benjamini-Hochberg). Fatos fixos: pior safra, comparação com a UF e tendência. A IA
  escreve resumo, interpretação, hipótese e próximas perguntas (com botão para perguntar no chat).
- **Previsão (treino):** por município e cultura: safras usadas, modelos testados, variáveis escolhidas com os
  coeficientes, equação treinada, erro da validação contra o da tendência, gráfico real × previsto safra a safra,
  previsão da safra que já teve chuva e aguarda o IBGE e da safra em andamento (com cenários seco, normal e chuvoso),
  comparação com a estimativa do IBGE, explicação da IA e histórico de treinos.
- **Alertas:** chuva acumulada da safra em andamento abaixo da média do mesmo trecho das safras passadas, e
  veranico onde aquele trecho costuma ter chuva. Cada alerta traz as safras passadas parecidas, o gráfico da chuva
  acumulada e a explicação da IA.

## Arquitetura

```
Navegador ──► frontend (nginx :8091) ──/api──► backend (FastAPI :8000) ──► ollama (:11434)  qwen3, com ferramentas
              React + Kole React                 │
                                                 ├──► postgres (:5432)  municípios, chuva, produção, coletas,
                                                 │                      descobertas, alertas e conversas
                                                 ├──► Open-Meteo        chuva diária e coordenadas (internet)
                                                 └──► IBGE              municípios, PAM e LSPA (internet)
```

| Serviço | Função | Porta no seu computador |
|---|---|---|
| `frontend` | nginx com o React; repassa `/api` ao backend (mesma origem, streaming sem buffer) | `127.0.0.1:8091` |
| `backend` | API, coletas, agendador, análises, treino da previsão, descobertas, alertas e chat com ferramentas | nenhuma |
| `ollama` | Modelo de linguagem | nenhuma |
| `ollama-init` | Baixa o modelo se faltar e termina | nenhuma |
| `postgres` | Todos os dados | nenhuma |
| `finetune-tools`, `finetune-train` | Dataset, avaliação e treino do fine-tuning (profile `finetune`, só quando você roda) | nenhuma |
| `gpu-tunnel` | Túnel SSH até a GPU externa (só com `compose.externo.yaml`, no lugar do `ollama`) | nenhuma |

O backend é dividido em `api/` (rotas finas) → `services/` (regras) → `repositories/` (SQL). O ciclo do chat:

```
pergunta ─► modelo (com a lista de ferramentas) ─► pede consultar_chuva(municipio, inicio, fim)
                                                       │
            resposta em streaming ◄── modelo ◄── resultado JSON calculado pelo código (SQL + Python)
```

O modelo pode pedir até `MAX_TOOL_ROUNDS` rodadas de ferramentas; na última, responde com o que tem. O raciocínio do
modelo (`CHAT_THINK`) fica desligado por padrão: num teste na CPU, a mesma chamada de ferramenta saiu igual e 6 vezes
mais rápida.

## Fontes de dados

| Dado | Fonte | Detalhe |
|---|---|---|
| Chuva diária | [Open-Meteo Historical](https://open-meteo.com/en/docs/historical-weather-api) | Reanálise ERA5 por latitude/longitude, desde 1940; os últimos dias vêm da [previsão](https://open-meteo.com/en/docs) e são trocados pelo arquivo quando ele chega (cerca de 5 dias de atraso). Licença CC BY 4.0; uso gratuito não comercial, com limite diário |
| Coordenadas | Open-Meteo Geocoding | Pelo nome do município e da UF |
| Municípios | [IBGE Localidades](https://servicodados.ibge.gov.br/api/docs/localidades) | Lista por UF e nome pelo código |
| Produção anual | [IBGE SIDRA, tabela 5457 (PAM)](https://sidra.ibge.gov.br/tabela/5457) | Município, UF e Brasil, desde 1974: área plantada (8331), área colhida (216), produção (214) e rendimento (112); soja 40124, milho 40122 |
| Estimativa da safra | [IBGE SIDRA, tabela 6588 (LSPA)](https://sidra.ibge.gov.br/tabela/6588) | Mensal, por UF e Brasil: soja 39443, milho 1ª safra 39441, milho 2ª safra 39442 |

Só saem do computador nomes de municípios, coordenadas, datas e códigos do IBGE. O backend só acessa esses
endereços (lista fixa em `backend/app/services/public_data.py`).

## Método

- **Janela da safra:** soja de outubro do ano anterior a março (a safra 2025 é a de 2024/25); milho de janeiro a
  abril, a fase da 2ª safra em que a chuva mais pesa. Maio e junho ficam de fora porque são secos todo ano. É uma
  escolha de método: mude em `backend/app/core/domain.py`.
- **Veranico:** maior sequência de dias com menos de 1 mm dentro da janela.
- **Desvio da tendência:** o rendimento sobe com a tecnologia. Comparar a chuva com o rendimento bruto mostraria a
  tecnologia, não o clima. Por isso a comparação usa a diferença entre o rendimento do ano e a reta de tendência.
- **Chuva da UF:** não existe "chuva média do estado" pronta. O sistema usa os `STATE_REFERENCE_COUNT` municípios que
  mais plantaram soja na UF, ponderados pela área plantada.
- **Descobertas:** correlação de Pearson com p-valor (teste t) e q-valor de Benjamini-Hochberg. Entram só as relações
  com `q ≤ DISCOVERY_MAX_Q`, `|r| ≥ DISCOVERY_MIN_ABS_R` e pelo menos `DISCOVERY_MIN_YEARS` safras.
- **Limites:** reanálise não é pluviômetro (quadrados de cerca de 25 km); 25 safras é pouco; o milho da PAM soma a 1ª
  e a 2ª safra; correlação não é causa.

## Configuração

Copie `.env.example` para `.env` e ajuste. Os scripts de inicialização criam o `.env` com `POSTGRES_PASSWORD` se ele
não existir. Depois de mudar o `.env`, rode o script de novo.

| Variável | Padrão | Para que serve |
|---|---|---|
| `APP_PORT` | `8091` | Porta do navegador |
| `APP_BIND` | `127.0.0.1` | `0.0.0.0` abre na rede local (veja [Segurança](#segurança-e-privacidade)) |
| `COMPOSE_FILE` | — | GPU NVIDIA local (`compose.yaml;compose.gpu.yaml`) ou GPU externa (`compose.yaml;compose.externo.yaml`); no Linux e no macOS, separe com `:` |
| `POSTGRES_PASSWORD` | — | Senha do banco (obrigatória; gerada pelos scripts) |
| `POSTGRES_DB` / `POSTGRES_USER` | `celke_agro` / `celke` | Banco e usuário |
| `CHAT_MODEL` | `qwen3:8b` | Modelo do Ollama; precisa aceitar ferramentas |
| `CHAT_NUM_CTX` | `8192` | Janela de contexto do modelo |
| `CHAT_TEMPERATURE` | `0.2` | Criatividade das respostas |
| `CHAT_THINK` | `false` | Raciocínio do modelo (`false`, `true` ou `auto`) |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | Tempo máximo de uma resposta do Ollama |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tempo que o modelo fica na memória depois da última pergunta |
| `HISTORY_MAX_MESSAGES` | `6` | Mensagens anteriores da conversa enviadas ao modelo |
| `MAX_TOOL_ROUNDS` | `5` | Rodadas de ferramentas por pergunta |
| `HISTORY_START_YEAR` | `2000` | Primeiro ano baixado de chuva e produção |
| `STATE_REFERENCE_COUNT` | `5` | Municípios de referência da chuva média da UF |
| `HTTP_TIMEOUT_SECONDS` | `60` | Tempo máximo de cada pedido ao Open-Meteo e ao IBGE |
| `SCHEDULER_ENABLED` | `true` | Liga as coletas automáticas |
| `SCHEDULER_TIMEZONE` | `America/Sao_Paulo` | Fuso do agendador |
| `RAIN_COLLECT_HOUR` | `6` | Hora da coleta diária de chuva |
| `MONTHLY_COLLECT_DAY` | `1` | Dia do mês da coleta de produção e estimativa |
| `DISCOVERY_MAX_Q` | `0.10` | q-valor máximo de uma descoberta |
| `DISCOVERY_MIN_ABS_R` | `0.4` | Correlação mínima, em módulo |
| `DISCOVERY_MIN_YEARS` | `8` | Safras mínimas para testar uma relação |
| `ALERT_RAIN_DEFICIT_PCT` | `25` | Chuva da safra abaixo da média que gera alerta (%) |
| `ALERT_DRY_SPELL_DAYS` | `10` | Dias seguidos sem chuva que geram alerta |
| `GPU_SSH` | — | Usuário e IP do servidor de GPU externa (`root@203.0.113.10`), com `compose.externo.yaml` |
| `GPU_SSH_PORT` | `22` | Porta SSH do servidor |
| `GPU_SSH_KEY` | `~/.ssh/id_ed25519` | Chave privada que o servidor aceita |
| `FINETUNE_BASE_MODEL` | `unsloth/Qwen3-8B` | Modelo base do fine-tuning (Hugging Face) |
| `FINETUNE_EPOCHS` | `2` | Passadas pelo dataset no fine-tuning |
| `FINETUNE_MAX_SEQ_LENGTH` | `4096` | Tamanho máximo de cada exemplo de treino, em tokens |

## Testes

Tudo no Docker:

```bash
docker compose --profile test run --rm --build backend-tests     # Ruff e pytest (com PostgreSQL de teste)
docker compose --profile test run --rm --build frontend-tests    # tsc e Vitest
docker compose --profile test rm -fs postgres-test
```

Os testes unitários usam dublês das fontes públicas e do modelo (`backend/tests/fakes.py`): não acessam a internet nem
o Ollama. O teste de integração usa tudo de verdade, com a stack no ar:

```bash
docker compose --profile test run --rm --build backend-tests pytest -m integration -v
```

## Comandos úteis

```bash
docker compose ps                               # situação dos containers
docker compose logs -f backend                  # coletas, agendador e erros
docker compose exec ollama ollama list          # modelos baixados
docker compose exec ollama ollama pull qwen3:14b
curl http://localhost:8091/api/collections      # fontes e registro das coletas
```

A documentação interativa da API fica em http://localhost:8091/api/docs.

## Hardware e escolha do modelo

| Computador | Modelo sugerido | Desempenho de referência |
|---|---|---|
| Sem GPU, 16 GB de RAM | `qwen3:8b` | Medido num Ryzen 7 5700: 7,9 tokens/s; pergunta com ferramentas em cerca de 1 minuto; relatório de descobertas em cerca de 3 minutos |
| GPU NVIDIA de 8 GB | `qwen3:8b` | Cabe inteiro na GPU |
| GPU NVIDIA de 12 GB (ex.: RTX 3060) | `qwen3:14b` | Escolhe ferramentas e interpreta melhor; o melhor para gravar o tutorial |
| Computador fraco ou sem GPU, mas com internet | `qwen3:14b` na [GPU externa](#gpu-externa-hostinger-e-similares) | Cobrado por hora; o resto do projeto continua local |
| Pouca memória | `qwen3:4b` | Mais rápido, erra mais a escolha das ferramentas |

O modelo precisa aceitar ferramentas (tool calling): no site do Ollama, a etiqueta **tools**. A página **Status e
coletas** avisa se o modelo configurado não aceitar.

Para trocar: mude `CHAT_MODEL` no `.env` e rode o script de inicialização de novo (o `ollama-init` baixa o modelo).

## Problemas comuns

| Sintoma | Causa provável e solução |
|---|---|
| O script fica parado em "Aguardando o modelo" | É o download. Acompanhe com `docker compose logs -f ollama-init` |
| "Não encontrei as coordenadas" no cadastro | O Open-Meteo não achou o município pelo nome. Tente de novo; se persistir, abra uma issue com o código IBGE |
| Coleta com erro "limite de pedidos atingido" | O Open-Meteo gratuito tem limite diário. Espere e use **Buscar agora** depois |
| Município parado em "Coletando" depois de reiniciar | A coleta foi interrompida e fica como erro; clique em **Coletar chuva agora** |
| Chat lento ou "demorou demais para responder" | Primeira pergunta carrega o modelo. Na CPU, use `qwen3:8b` ou menor; com GPU, ligue o `compose.gpu.yaml` |
| "O modelo não aceita ferramentas" | Troque `CHAT_MODEL` por um modelo com a etiqueta tools |
| "GPU externa desconectada" no Status | Veja `docker compose logs gpu-tunnel`: IP, porta, chave ou a instância desligada no painel |
| Treino remoto para em "Conferindo a GPU" | O servidor não aceitou a chave SSH ou não tem driver NVIDIA; confira o tipo da instância |
| Página não abre na porta 8091 | Outra aplicação usa a porta: mude `APP_PORT` no `.env` |

## Segurança e privacidade

- Só a porta do frontend é publicada, em `127.0.0.1`. Ollama, PostgreSQL e backend não têm porta publicada.
- Não há login. Se mudar `APP_BIND` para `0.0.0.0`, qualquer pessoa da rede local usa o sistema.
- A senha do banco fica só no `.env` (fora do git).
- O backend só acessa os endereços do Open-Meteo e do IBGE, por HTTPS, e só envia parâmetros de consulta.
- O modelo não escreve SQL nem executa comandos: escolhe uma das 10 ferramentas, e os argumentos são validados.
- Os resultados das ferramentas são tratados como dado, não como instrução.

## Evolução do projeto

Sugestões para próximas etapas do tutorial:

- **Cálculo por talhão:** cadastro de fazenda e talhões (KML ou GeoJSON), chuva estimada por satélite (CHIRPS, cerca
  de 5,5 km) e chuva medida por pluviômetro ou estação (com prioridade), produção por talhão vinda da fazenda e os
  mesmos três papéis da IA no nível do talhão. Extra: vigor da lavoura por talhão com o Sentinel-2 (NDVI).
- **Previsão por talhão:** treinar o modelo de previsão com a produtividade de cada talhão, quando a fazenda tiver
  esse histórico.

## Estrutura do projeto

```
backend/
  app/api/            rotas: status, municípios, coletas, análises, descobertas e alertas, chat, conversas
  app/core/           configuração, erros, domínio (UFs, culturas, janelas, glossário), container
  app/repositories/   PostgreSQL (esquema em database.py)
  app/services/       public_data (Open-Meteo e IBGE), collection_service, scheduler, seasons, statistics,
                      analysis_service, charts, features, forecast_model e forecast_service (previsão treinada),
                      tools, chat_service, insight_service, ollama_service
  app/finetune/       dataset e avaliação do fine-tuning (python -m app.finetune)
  tests/              unitários (com dublês) e integração
frontend/
  src/pages/          Análises, Previsão, Chat, Descobertas, Alertas, Municípios, Status e coletas
  src/components/     ChartView (especificação do backend → gráfico do Kole)
  src/services/       cliente da API e leitor do streaming
finetuning/           treino LoRA na GPU (Dockerfile, treinar.py), treinar_remoto.sh (GPU externa) e
                      criar_modelo.sh para o Ollama
compose.externo.yaml  modelo do chat na GPU externa, pelo túnel SSH
docs/
  prompts/            as etapas do tutorial, em texto
  prompts-iniciais/   prompts que recriam o projeto do zero com o conteúdo exato dos arquivos (gerados)
  gerador-prompts/    gera e confere prompts-iniciais/
scripts/              iniciar.sh e iniciar.ps1
```

## Prompts para recriar o projeto

O projeto pode ser recriado do zero por um agente de IA com acesso ao terminal (Claude Code ou similar):

- [`docs/prompts-iniciais/`](docs/prompts-iniciais/README.md): pasta autossuficiente. Copie só ela para uma pasta
  vazia e execute `prompts-iniciais/prompt-para-replicar-projeto.md`. Os prompts trazem o conteúdo de todos os
  arquivos.
- [`docs/prompts/`](docs/prompts/README.md): as mesmas etapas descritas em texto, para gravar o tutorial.

## Licença

[MIT](LICENSE.txt).
