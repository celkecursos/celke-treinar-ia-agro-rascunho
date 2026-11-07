# Etapa 7 — Integração ponta a ponta

## Contexto

Teste o Celke Treinar IA Agro como um usuário faria, com as APIs públicas e o modelo real. Não há arquivos novos. Se
algo falhar, corrija a causa, repita a verificação e relate o que mudou. Não apague nada além do que você mesmo criar
neste teste.

Crie o teste de integração `backend/tests/integration/test_full_flow.py` (marcado com `@pytest.mark.integration`):
cadastra Rio Verde (GO, código 5218805) se não existir, espera a coleta terminar, confere chuva (mais de 3.000 dias) e
produção (2023 ou depois), confere a análise da soja (correlação e 7 gráficos), faz uma pergunta no chat que exige
ferramenta e confere `tool_call` e `done`; no fim, apaga a conversa e o município se foi ele que cadastrou.

## Verificação

1. Duas vezes, para confirmar que a segunda não baixa nada: `sh scripts/iniciar.sh` (ou o `iniciar.ps1`). Termina com
   "Pronto! Abra http://localhost:8091".
2. `docker compose --profile test run --rm --build backend-tests pytest -m integration -v` (1 passou) e
   `docker compose --profile test rm -fs postgres-test`.
3. Cadastre um município pela API e acompanhe a situação até `pronto`; confira em `/api/collections` as coletas de
   chuva, produção e estimativa com origem `cadastro`.
4. `POST /api/collections/producao` duas vezes seguidas: a primeira é aceita (202) e a segunda recusada (409)
   enquanto a primeira coleta; ao terminar, a mensagem é "Já está atualizado…".
5. `GET /api/forecasts/<código>/milho`: há treino, com o erro do modelo e o da tendência; `POST /api/forecasts/train`
   cria outro treino no histórico.
6. Pergunte no chat "A chuva de abril influencia o rendimento do milho em <município>?" e confira a ferramenta
   `correlacao_chuva_rendimento` com `variavel: chuva_do_mes` e `mes: 4`, e a resposta com r e a fonte.
7. Persistência: `docker compose down` (**sem** `-v`), rode o script de novo e confira que o município, as coletas, os
   treinos e as conversas continuam.
8. Apague a conversa e o município do teste.
