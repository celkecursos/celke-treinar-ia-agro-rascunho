# Etapa 3 — Treinar o modelo de previsão da safra

## Contexto

O backend já coleta chuva e produção e calcula as safras (etapa 2). Nesta etapa a IA é **treinada de verdade**: um
modelo aprende, com as safras passadas do município, como o rendimento (kg/ha) responde ao ano e à chuva, é testado
em safras que não viu e prevê a safra que ainda não tem número do IBGE e a safra em andamento. O treino roda sozinho
depois de cada coleta com dado novo e pelo botão.

A ideia central para o tutorial: **um modelo só vale se for medido**. Toda previsão vem com o erro da validação e a
comparação com o jeito mais simples de prever (a tendência sozinha).

## Variáveis de chuva (`services/features.py`)

Para cada cultura: chuva da safra (passo de 100 mm), maior veranico (passo de 5 dias) e a chuva de cada mês da janela
(passo de 50 mm). Cada variável tem chave, rótulo, unidade e uma função que lê o valor de uma safra. As mesmas
variáveis servem às descobertas da etapa 4.

## Modelo (`services/forecast_model.py`, funções puras)

```
rendimento (kg/ha) = intercepto + b·ano + c₁·variável₁ + c₂·variável₂
```

- `solve`: sistema linear por eliminação de Gauss com pivoteamento.
- `fit`: mínimos quadrados com as variáveis padronizadas (e regularização mínima, só para estabilidade), devolvendo
  os coeficientes em unidades originais.
- `leave_one_out`: cada safra prevista por um modelo treinado com todas as outras.
- `train(amostras, candidatas, mínimo)`: testa a tendência sozinha e todas as combinações de 1 e 2 variáveis de chuva,
  cada uma com as safras que têm todos os valores e com a tendência comparada nas mesmas safras; escolhe a de menor
  erro médio absoluto na validação. Se a melhor não reduzir o erro em pelo menos 5% (`MIN_GAIN`), fica só com a
  tendência. Guarda as médias das variáveis: a "tendência" de um ano é a previsão com a chuva na média.

## Serviço (`services/forecast_service.py`)

- Treina cada município cadastrado × cultura com pelo menos `DISCOVERY_MIN_YEARS` safras.
- **Safra com chuva completa e sem PAM** (ex.: a soja colhida este ano): previsão com faixa de ± erro médio.
- **Safra em andamento**: a chuva real até o último dia e o resto da janela emprestado de cada safra passada
  (alinhado pelo início da janela); cada combinação vira uma safra sintética e uma previsão. Os cenários seco, normal
  e chuvoso são os terços pela chuva da safra; a faixa vai do 10º ao 90º percentil, nunca menor que ± o erro médio.
- Comparação com a LSPA da UF no mesmo ano (no milho, produção da 1ª e da 2ª safra somadas, dividida pela área).
- Resultado guardado em `forecast_models` (município, cultura, origem `coleta` ou `botao`, modelo, resultado JSONB,
  explicação), mantendo os 20 últimos treinos de cada par: variáveis com coeficientes, equação com os sinais certos
  ("− 94,94·maior veranico"), safras usadas, modelos testados, erros do modelo e da tendência, ganho, validação safra
  a safra, previsões e dois gráficos (real × previsto × tendência; cenários com a tendência como referência).
- Trava: um treino por vez; o botão recebe 409 se já houver treino.

## Rotas

- `GET /api/forecasts/{código}/{cultura}`: último treino, histórico (data, origem, safras, variáveis, erros) e se há
  treino em andamento. 404 para município não cadastrado.
- `POST /api/forecasts/{código}/{cultura}/train`: treina de novo só esse município e cultura, em segundo plano (202).
  Município ou cultura que não existem dão 404 na hora; outro treino em andamento dá 409. É o que o botão da tela
  usa: mais rápido e mais fácil de mostrar.
- `POST /api/forecasts/train`: treina de novo todos os municípios e culturas, em segundo plano (202).

## Testes

`solve` e `fit` recuperando coeficientes conhecidos; a validação não vê a safra prevista; o treino escolhe a chuva
quando ela explica o rendimento e fica só com a tendência quando não explica; mínimo de safras; depois do cadastro,
o treino existe, usa a chuva, erra menos que a tendência e tem a safra em andamento com os três cenários; o
treino por município e cultura só cria histórico nesse par.

## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile test rm -fs postgres-test
```
