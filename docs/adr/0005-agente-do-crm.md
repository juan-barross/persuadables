# ADR 0005: agente do CRM só lê os relatórios versionados

**Status:** aceita

## Contexto

O gerente de CRM faz perguntas que mudam a cada reunião: "e se o contato custar ₽ 5?", "qual o
efeito em quem gasta pouco?". O simulador responde parte delas, mas não perguntas sobre os
segmentos ou os modelos. Um agente com Opus 5.5 pode responder em texto, desde que não invente
número.

## Decisão

- O agente tem duas ferramentas: `consultar`, que roda um `SELECT` nas tabelas de `reports/`
  (efeito, segmentos, CUPED, modelos, influenciados e curvas), e `lucro`, que chama
  `decisao.financeiro`, a mesma função do simulador.
- Ele não acessa a base da X5. Tudo o que lê está versionado no git, então funciona num clone
  sem baixar dados, e cada resposta pode ser conferida contra um arquivo.
- As ferramentas usam `strict: true`, e `consultar` recusa qualquer comando que não seja um
  único `SELECT`.
- A avaliação usa dez perguntas com resposta calculada a partir dos próprios relatórios, não
  digitada à mão, e conta acerto com erro de até 1%.
- O modelo vem de `PERSUADABLES_MODELO` (padrão `anthropic/claude-opus-5.5` pela OpenRouter,
  ou `claude-opus-5-5` direto na Anthropic sem chave da OpenRouter).

## Consequências

- Os testes usam um cliente simulado, então a CI não gasta chave.
- A OpenRouter reserva `max_tokens` vezes o preço a cada chamada; com saldo baixo ela recusa
  com 402. Por isso `max_tokens` fica em 4.096, que sobra para respostas curtas.
