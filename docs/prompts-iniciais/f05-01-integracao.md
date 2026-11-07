# Integração ponta a ponta

**Etapa:** 5 de 6
**Requer:** etapa 4

## Orientação antes de começar

> **O que vai acontecer agora:** vou testar o fluxo completo com os dados públicos e o modelo real: coletar,
> analisar, treinar a previsão, perguntar no chat, reiniciar e ver se os dados continuam. **O que você precisa
> fazer:** nada.

## Prompt

Teste o **Celke Treinar IA Agro** como um usuário faria. Não há arquivos novos. Use os scripts criados na etapa 1, e no
Windows o `iniciar.ps1`. Se algo falhar, corrija a causa, repita a verificação e relate o que mudou.
Não apague nada além do que você mesmo criar neste teste.

## Verificação

1. Duas vezes, para confirmar que a segunda não baixa nada: `sh scripts/iniciar.sh` ou
   `powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1`. Termina com "Pronto! Abra http://localhost:<porta>".
2. `docker compose --profile test run --rm --build backend-tests pytest -m integration -v` (1 passou) e
   `docker compose --profile test rm -fs postgres-test`.
3. `GET /api/collections`: coletas de chuva, produção e estimativa com origem `cadastro`. `POST /api/collections/producao`
   duas vezes seguidas: 202 e depois 409; ao terminar, a mensagem "Já está atualizado…".
4. `GET /api/forecasts/5218805/milho`: há treino, com o erro do modelo e o da tendência. `POST /api/forecasts/train` e,
   depois de alguns segundos, o histórico tem um treino a mais, com origem `botao`.
5. Pergunte no chat (use `curl.exe`, `-N` e o JSON em arquivo no Windows):
   ```bash
   curl -N -X POST http://localhost:<porta>/api/chat -H "Content-Type: application/json" -d '{"question":"A chuva de abril influencia o rendimento do milho em Rio Verde?"}'
   ```
   Confira o evento `tool_call` com `correlacao_chuva_rendimento`, `"variavel": "chuva_do_mes"` e `"mes": 4`, e a
   resposta com r e a fonte, sem raciocínio na tela.
6. Persistência: `docker compose down` (**sem** `-v`), rode o script de novo e confira que `/api/municipalities`,
   `/api/collections`, `/api/forecasts/5218805/milho` e `/api/conversations` continuam com os dados.
7. Exclua, pelo id, as conversas criadas neste teste.

## Depois de executar

Só há commit se algo foi corrigido, com a mensagem `fix: <o que foi corrigido>`.

## Orientação ao terminar

> **Pronto:** o fluxo completo foi testado com os dados públicos e o modelo real. Falta só a documentação. Continue sem
> fazer nada.
