# Etapa 8 — Documentação e guia para agentes

## Contexto

Crie o `README.md` e o `CLAUDE.md` do Celke Treinar IA Agro. O público do README é quem baixou o projeto do GitHub e
quem vai assistir ao tutorial "Como treinar IA com dados do agro".

## `README.md`

Na ordem:

1. Título e um parágrafo: IA local que coleta chuva (Open-Meteo) e produção de soja e milho (IBGE) e **treina dois
   modelos** com esses dados, além de responder, descobrir e avisar.
2. **Como executar (quem baixou do GitHub)**: o que precisa (Docker, Git, internet, RAM, disco), `git clone`,
   `./scripts/iniciar.sh` ou o `iniciar.ps1`, o que esperar da primeira vez (download do modelo), GPU com
   `COMPOSE_FILE`, o roteiro no navegador página a página e os comandos para parar, voltar e apagar.
3. **Os dois treinamentos**: tabela previsão da safra × fine-tuning (o que aprende, dados, como treina, como mede,
   quando treina, onde aparece), um exemplo real com números, o que **não** é treinado (números ficam no banco e nas
   ferramentas) e os três papéis da IA (responder, descobrir, avisar).
4. **Fine-tuning do modelo de linguagem (GPU)**: os 5 comandos (exportar, avaliar antes, treinar, criar o modelo,
   avaliar depois), como escolher o `celke-agro` na página **Modelo de IA** (botão **Configurar** no Status) e o que esperar.
5. Funcionalidades, arquitetura (diagrama e tabela de serviços), fontes de dados (com licença e limite do
   Open-Meteo), método (janelas, veranico, desvio da tendência, chuva da UF, filtro das descobertas, limites),
   configuração (tabela de todas as variáveis), testes, comandos úteis, hardware e escolha do modelo (troca pelo
   página Modelo de IA e o que conferir num modelo maior: memória, tempo, contexto e base do fine-tuning), problemas
   comuns, segurança e privacidade, evolução do projeto (talhão, previsão por talhão), estrutura e os prompts.

## `CLAUDE.md`

Convenções para agentes e desenvolvedores: a tabela das pastas e stacks; branches e commits (`main`, `homolog`,
`feature/…`; commit só quando pedirem, Conventional Commits em português, sem coautoria); a regra central (o código
calcula, o modelo interpreta; ferramenta nova com Pydantic, `TOOL_SPECS`, `_handlers`, números prontos, `fonte`,
`summary` e nomes de campo explícitos; glossário); os dois treinamentos e o que manter ao mudar cada um; regras
gerais (Docker, idiomas, segredos, variáveis em quatro lugares, portas, endereços permitidos); backend (camadas, erros,
coletas, agendador, eventos do chat, gráficos, testes); frontend (Kole do npm, estilos, ícones,
API); prompts do tutorial (originais, sem datas; `docs/prompts-iniciais` gerado e conferido).

## Verificação

```bash
docker compose config -q && echo ok
git status --short    # .env não aparece
```

Confira que os links internos do README existem (`.env.example`, `LICENSE.txt`, `docs/prompts-iniciais/README.md`,
`docs/prompts/README.md`).
