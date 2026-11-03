# Prompts iniciais

Prompts para criar o **Celke Treinar IA Agro** do zero com um agente de IA com acesso ao terminal (Claude Code ou
similar): IA local que coleta chuva e produção de soja e milho de fontes públicas, treina um modelo de previsão da
safra e um fine-tuning LoRA do modelo de linguagem, com backend Python, frontend React com o layout
`@celke/kole-react` e Docker.

**Esta pasta basta sozinha.** Você não precisa de nenhum outro arquivo do projeto: os prompts trazem o código, o README, a
licença, o guia para agentes, os scripts e a configuração do Docker. O `package-lock.json` e os segredos do `.env` são gerados
durante a execução.

## O que você precisa antes

| O quê | Observação |
|---|---|
| Claude Code (ou agente similar) | Com acesso ao terminal |
| Docker Desktop (Windows, macOS) ou Docker Engine (Linux) | Se faltar, o prompt mostra como instalar |
| Git | Se faltar, o prompt mostra como instalar |
| Internet | Para baixar imagens, o modelo e os dados públicos |
| Disco | Cerca de 10 GB mais o modelo (mais 25 GB para o fine-tuning, com GPU) |
| GPU NVIDIA (opcional) | Acelera o chat e é necessária para o treino LoRA; sem ela, dá para alugar uma por hora (GPU externa) |

**Não instale o Ollama, o Python nem o Node.** Tudo roda no Docker.

## Como usar

1. Crie uma pasta vazia para o projeto, em qualquer lugar, e copie só esta pasta `prompts-iniciais` para dentro dela.
2. Abra o Docker e espere ele iniciar.
3. Abra o Claude Code na pasta do projeto e execute:

   ```text
   Execute o prompt prompts-iniciais/prompt-para-replicar-projeto.md
   ```

4. Selecione o modelo de IA na pergunta e, se o Git não estiver configurado, preencha nome e e-mail. O prompt confere a
   memória, a GPU e o disco do seu computador e recomenda um modelo, com outras opções, inferior e superior.
5. Espere. O agente avisa o que está fazendo e o que você precisa fazer. No fim, ele mostra como testar no navegador.

Se parar no meio, execute o mesmo comando numa sessão nova: o andamento fica em `prompts-iniciais/progresso.md`.

Para gravar o tutorial etapa por etapa, execute os prompts da tabela um a um, cada um numa sessão nova, seguindo a
**Verificação** e o **Depois de executar** de cada um. Cada etapa precisa da anterior concluída.

| Ordem | Prompt | Resultado |
|---|---|---|
| 0 | [Preparação e escolha do modelo](f00-01-preparacao-e-modelo.md) | Computador conferido, modelo escolhido, `.env` e licença |
| 1 | [Estrutura inicial e Docker](f01-01-estrutura-e-docker.md) | Compose, scripts, Ollama, PostgreSQL e modelo baixado |
| 2 | [Backend](f02-01-backend.md) | Coletas, agendador, análises, previsão treinada, chat com ferramentas, descobertas, alertas e testes |
| 3 | [Frontend React com o Kole](f03-01-frontend-kole.md) | Análises, Previsão, Chat, Descobertas, Alertas, Municípios e Status |
| 4 | [Fine-tuning do modelo de linguagem](f04-01-fine-tuning.md) | Dataset, avaliação antes e depois e treino LoRA (na GPU) |
| 5 | [Integração ponta a ponta](f05-01-integracao.md) | Fluxo completo com os dados públicos e o modelo real, persistência |
| 6 | [Documentação e entrega](f06-01-documentacao.md) | README, guia para agentes, prompts em `docs/` e commit final |

## O que já está decidido

Para você ter o mínimo de perguntas, os prompts já decidem: tecnologias e versões, porta (`8091` ou a próxima livre), uso da
GPU NVIDIA quando disponível, licença MIT com o seu nome do Git, senha aleatória e commits locais.
Você só responde: **qual modelo de IA usar** (selecionando uma opção) e, se o Git ainda não estiver configurado, **o seu nome
e e-mail** (preenchendo os campos).
