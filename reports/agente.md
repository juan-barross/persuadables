# Agente de perguntas do CRM

Gerado por `persuadables avaliar-agente`. Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free`.

O agente responde perguntas do gerente de CRM usando duas ferramentas: `consultar`, que lê as
tabelas de resultado em `reports/`, e `lucro`, que roda a mesma conta do simulador. As respostas
certas vêm dos próprios relatórios, e uma resposta conta como acerto quando erra no máximo
1%.

**9 de 10 acertos**, com 45,808 tokens no total (cerca de US$ 0.00).

| pergunta | esperado | resposta | acertou |
|---|---|---|---|
| Qual foi o efeito médio da campanha na taxa de compra, em pontos percentuais? | 3.3231 | 3.3231 | True |
| Quantos compradores a mais a campanha gerou entre os clientes tratados? | 3,322.45 | 3,322.45 | True |
| Qual o efeito da campanha, em p.p., no decil de clientes que menos gastavam antes? | 7.2193 | 7.2193 | True |
| Qual a AUUC do S-learner no conjunto de teste? | 0.0148 | 0.0148 | True |
| Qual a mediana de idade dos 20% de clientes com maior uplift previsto? | 58 | 58 | True |
| Quantos compradores a mais teremos mandando por uplift para 20% da base? | 2,740.9 | 2,740.9 | True |
| Qual o lucro incremental de mandar por uplift para 15% da base, com contato a 3 rublos e margem de 20%? | 159,783 | 159,783 | True |
| Com contato a 5 rublos e margem de 25%, qual o lucro de mandar por propensão para 30% da base? | -160,436 | -160,436 | True |
| Qual o lucro de mandar a campanha para a base inteira com contato a 6 rublos e margem de 20%? | -540,927 | -540,927 | True |
| Com contato a 6 rublos e margem de 20%, qual porcentagem da base devemos contatar por uplift para ter o maior lucro? Responda em %. | 10 |  | False |
