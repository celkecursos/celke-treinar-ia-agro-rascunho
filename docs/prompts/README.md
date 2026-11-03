# Prompts do Celke Treinar IA Agro

Prompts para criar o Celke Treinar IA Agro do zero com um agente de IA que tenha acesso ao terminal (Claude Code ou
similar): IA local que coleta chuva (Open-Meteo) e produção de soja e milho (IBGE), treina um modelo de previsão da
safra e um fine-tuning LoRA do modelo de linguagem, e usa o Ollama com ferramentas para responder, descobrir e
avisar. Backend Python com FastAPI, frontend React com o layout `@celke/kole-react`, PostgreSQL e Docker Compose.

## Antes de começar

- Docker com o Docker Compose em execução (`docker compose version`).
- Git.
- Internet: as etapas baixam imagens Docker, pacotes do npm e do PyPI, o modelo (de 5 a 9 GB) e os dados públicos.
- 16 GB de RAM (modelo na CPU), GPU NVIDIA ou uma GPU externa alugada por hora (a etapa 0 recomenda).

## Como usar

**Opção 1: tudo numa execução.** Crie uma pasta vazia para o projeto, copie esta pasta `prompts` para dentro dela,
abra o agente na pasta do projeto e digite:

```text
Execute o prompt prompts/prompt-para-replicar-projeto.md
```

O [prompt para replicar o projeto](prompt-para-replicar-projeto.md) executa as etapas da tabela na ordem, cada uma
num subagente com contexto limpo, confere a **Verificação** de cada etapa antes da próxima e registra o andamento em
`prompts/progresso.md`. Se parar no meio, execute o mesmo comando numa sessão nova e ele continua de onde parou.

**Opção 2: etapa por etapa** (para gravar o tutorial). Execute os prompts da tabela um a um, cada um numa sessão
nova do agente, na pasta do projeto. Siga a **Verificação** de cada prompt antes de passar para o próximo.

| Ordem | Prompt | Resultado |
|---|---|---|
| 0 | [Preparação e escolha do modelo](00-preparacao-e-modelo.md) | Capacidade do computador conferida, modelo do chat e lugar do treino escolhidos, `.env` e licença |
| 1 | [Estrutura inicial e Docker](01-estrutura-e-docker.md) | Pastas, `compose.yaml` com Ollama e PostgreSQL, download do modelo, `.env.example`, scripts |
| 2 | [Coleta de dados e análises](02-coleta-e-analises.md) | API FastAPI, clientes do Open-Meteo e do IBGE, cadastro de municípios, coletas com registro, agendador, análises com estatística e gráficos, testes |
| 3 | [Treinar o modelo de previsão da safra](03-previsao-treinada.md) | Regressão treinada com as safras, validação deixando uma de fora, comparação com a tendência, cenários, histórico de treinos |
| 4 | [IA com ferramentas: responder, descobrir e avisar](04-ia-com-ferramentas.md) | Chat com tool calling (10 ferramentas), conversas, descobertas com filtro estatístico, alertas, explicação da IA nos treinos |
| 5 | [Frontend React com o Kole](05-frontend-kole.md) | Análises, Previsão, Chat, Descobertas, Alertas, Municípios e Status com o `@celke/kole-react` e os gráficos dele |
| 6 | [Fine-tuning do modelo de linguagem](06-fine-tuning.md) | Dataset de perguntas → ferramentas, avaliação antes e depois, treino LoRA na GPU local ou externa, modelo `celke-agro` no Ollama |
| 7 | [Integração ponta a ponta](07-integracao.md) | Fluxo completo com as APIs públicas e o modelo real, persistência |
| 8 | [Documentação e guia para agentes](08-documentacao.md) | `README.md` completo e `CLAUDE.md` |

Cada prompt termina com a seção **Verificação**: os comandos precisam ser executados de verdade e passar antes da
próxima etapa.

## Regras que valem para todas as etapas

- Nomes de classes, funções, variáveis e arquivos em inglês; interface, mensagens e documentação em português do
  Brasil.
- Tudo roda no Docker; nenhuma etapa pode exigir Python ou Node instalados para executar ou testar.
- **O código calcula, o modelo interpreta.** Somas, médias, tendência, correlação e p-valor ficam no código. O modelo
  escolhe ferramentas de uma lista fechada e escreve texto.
- Dois treinamentos de verdade, sempre com medição: o modelo de previsão (etapa 3) é validado deixando uma safra de
  fora e comparado à tendência; o fine-tuning (etapa 6) é medido com perguntas que não estão no treino, antes e
  depois. O fine-tuning ensina comportamento (escolher ferramentas), nunca números.
- Não faça commit nem push, a não ser que a pessoa peça. Se pedir, mensagens em Conventional Commits em português,
  sem coautoria nem menção a ferramenta de IA.
