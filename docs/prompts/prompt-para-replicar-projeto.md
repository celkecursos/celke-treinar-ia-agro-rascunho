# Prompt para replicar o projeto

Cria o Celke Treinar IA Agro completo numa execução só: a sessão do agente coordena e cada etapa da tabela do
[README](README.md) é executada por um subagente com contexto limpo.

## Antes de executar

- Uma pasta vazia para o projeto, com a pasta `prompts` dentro dela.
- Docker com o Docker Compose em execução.
- Internet e cerca de 20 GB livres em disco.

Abra o agente na pasta do projeto e digite:

```text
Execute o prompt prompts/prompt-para-replicar-projeto.md
```

## Prompt

Você vai construir o Celke Treinar IA Agro executando, **na ordem**, as etapas da tabela do `README.md` da pasta de
prompts, sem parar entre elas. Só pare nos casos listados em **Quando parar**.

Nomes usados abaixo:

- **raiz**: o diretório atual, onde o projeto é criado.
- **pasta de prompts**: a pasta que contém este arquivo. Use caminhos relativos à raiz.

Você é o **coordenador**: não execute as etapas no seu próprio contexto.

### Preparação

1. **Progresso**: leia `progresso.md` na pasta de prompts. Se existir, retome a partir da primeira etapa que não
   está concluída.
2. **Pasta vazia**: se a raiz tiver arquivos além da pasta de prompts e não houver `progresso.md`, pare e avise: é
   um projeto existente, e as etapas gravariam por cima dele.
3. **Git**: se a raiz não for um repositório, execute `git init -b main`. Acrescente
   `/<pasta de prompts>/progresso.md` em `.git/info/exclude`.
4. **Docker**: confira `docker compose version` e `docker info`. Se o Docker não estiver rodando, pare e peça para a
   pessoa iniciá-lo.

### Etapa 0

Execute `00-preparacao-e-modelo.md` você mesmo, nesta sessão, porque ela conversa com o usuário (capacidade do
computador, modelo de IA, onde treinar). As demais etapas usam os valores de `docs/configuracao.md`.

### Para cada etapa (1 em diante)

1. Leia o arquivo da etapa e passe o conteúdo **inteiro** a um subagente novo, com esta instrução no início: "Você
   está na raiz do projeto Celke Treinar IA Agro. Execute o prompt abaixo por completo, incluindo a seção
   Verificação. Ao terminar, responda com a lista de arquivos criados ou alterados e a saída resumida de cada comando
   da Verificação."
2. Quando o subagente terminar, rode você mesmo os comandos da **Verificação** da etapa. Se algum falhar, mande o
   mesmo subagente (ou um novo, com a saída do erro) corrigir e verifique de novo. Faça no máximo três tentativas.
3. Registre em `progresso.md`: número da etapa, `concluída` e o resultado da verificação em uma linha.

### Quando parar

- Uma verificação falhou três vezes seguidas.
- O Docker parou de responder ou falta espaço em disco.
- Um download (imagem, pacote, modelo ou dado público) falhou por falta de internet.

Ao parar, diga qual etapa, o comando que falhou e a saída do erro.

### No fim

Mostre o endereço da aplicação (`http://localhost:8091`), o resultado das verificações de cada etapa e os comandos
para parar (`docker compose stop`) e apagar tudo (`docker compose down -v`). Não faça commit: a pessoa decide quando
commitar.
