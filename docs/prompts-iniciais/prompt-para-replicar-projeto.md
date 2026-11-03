# Prompt para replicar o projeto

Cria o Celke Treinar IA Agro completo numa execução só: a sessão do agente coordena, e cada etapa da tabela do
[README](README.md) é executada com contexto limpo.

## Antes de executar

Uma pasta vazia para o projeto, com `prompts-iniciais` dentro dela, e o Docker aberto. Na pasta do projeto, digite:

```text
Execute o prompt prompts-iniciais/prompt-para-replicar-projeto.md
```

## Prompt

Você vai construir o **Celke Treinar IA Agro** executando, **na ordem**, as etapas da tabela do `README.md` da pasta de
prompts. Execute tudo automaticamente. Só pare nos casos de **Quando parar**. A pessoa pode não ser técnica: em toda
mensagem, deixe claro o que está acontecendo e **o que ela precisa fazer** (muitas vezes, nada).

Nomes usados abaixo:

- **raiz**: o diretório atual, onde o projeto é criado.
- **pasta de prompts**: a pasta que contém este arquivo. Use caminhos relativos à raiz.

### Ao começar

1. Leia `progresso.md` na pasta de prompts. Se existir, diga de qual etapa vai continuar e pule as concluídas.
2. Mostre ao usuário:
   > **Vou criar o Celke Treinar IA Agro no seu computador.** São 7 etapas, e a mais demorada é o download do modelo de IA.
   > **O que você precisa fazer:** logo no início, selecionar o modelo e, se for preciso, preencher nome e e-mail do Git.
   > Depois, só deixar o Docker aberto.
   > Avisarei sempre que precisar de você. Se parar no meio, é só executar este prompt de novo.

### Etapas

1. **Etapa 0:** execute `f00-01-preparacao-e-modelo.md` você mesmo, nesta sessão, porque ela conversa com o usuário.
2. **Etapas 1 a 6:** para cada uma, nesta ordem:
   1. Mostre ao usuário a seção **Orientação antes de começar**, trocando os marcadores pelos valores de
      `docs/configuracao.md`.
   2. Dispare um subagente, em sequência e nunca em paralelo, com esta instrução. Sem subagentes disponíveis, execute você
      mesmo:
      > Leia `<pasta de prompts>/<arquivo>.md` e execute a seção `## Prompt` exatamente como está escrita, na raiz deste
      > repositório. Crie os arquivos com **exatamente** o conteúdo indicado. Rode a seção `## Verificação` e corrija o que
      > falhar. Não faça commit. Você não consegue falar com o usuário: não faça perguntas; a sua resposta final vai para o
      > coordenador. Responda com: arquivos criados, resultado de cada verificação, pendências e qualquer desvio do prompt.
   3. Leia o relatório e rode de novo os comandos principais da **Verificação**. Se algo falhar, mande corrigir e verifique de
      novo, em até três tentativas.
   4. Execute a seção `## Depois de executar`, sem `Co-Authored-By` nem menção a ferramenta de IA nas mensagens.
   5. Registre em `progresso.md`: etapa, arquivo, commit, `concluída` e pendências.
   6. Mostre ao usuário a seção **Orientação ao terminar**.

Se uma etapa levar muito tempo, como no download do modelo, avise o usuário de tempos em tempos, com o que está em andamento.

### Quando parar

- A etapa 0 pediu, ou falta a resposta das perguntas dela.
- Uma verificação falhou três vezes seguidas.
- O Docker parou de responder, acabou o espaço em disco ou caiu a internet.

Ao parar, diga em linguagem simples o que aconteceu, **o que a pessoa precisa fazer** e que depois basta executar este prompt de
novo. Não invente valores nem apague volumes ou dados que já existiam. O treino LoRA sem GPU NVIDIA não é motivo para parar:
é uma pendência registrada.

### Regras

- Não pule etapas nem "melhore" os arquivos: o conteúdo já foi testado junto.
- Nunca mostre a chave do `.env`.
- Não faça push.
- No fim, mostre a **Orientação ao terminar** da etapa 6 e as pendências do `progresso.md`.
