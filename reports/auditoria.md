# Auditoria dos dados da X5

Gerado por `campanha auditar` sobre `data/parquet`. Data de corte: 2019-03-19.

## 01_contagens

| verificacao | valor |
|---|---|
| linhas em clients | 400,162 |
| linhas em uplift_train | 200,039 |
| linhas em purchases (itens) | 45,786,568 |
| transações distintas | 8,045,201 |
| clientes distintos com compra | 400,162 |
| clientes do experimento sem nenhuma compra | 0 |
| clientes do experimento tratados | 99,981 |
| clientes do experimento que compraram depois (target = 1) | 124,002 |

## 02_chaves

| verificacao | valor |
|---|---|
| itens de compra sem cliente em clients | 0 |
| clientes do experimento ausentes de clients | 0 |
| client_id repetido em clients | 0 |
| client_id repetido em uplift_train | 0 |
| treatment_flg fora de {0, 1} | 0 |
| target fora de {0, 1} | 0 |
| transações com mais de um cliente, loja ou horário | 28 |
| transações com purchase_sum diferente entre os itens | 28 |
| itens repetidos (mesma transação e produto) | 3 |

## 03_datas

| verificacao | valor |
|---|---|
| primeira compra | 2018-11-21 21:02:33 |
| última compra | 2019-03-18 23:40:03 |
| data de corte usada | 2019-03-19 00:00:00 |
| itens de compra na data de corte ou depois (vazamento em potencial) | 0 |
| itens de compra antes de 2000 ou sem data | 0 |
| clientes com cartão emitido na data de corte ou depois | 0 |
| clientes com primeiro resgate antes da emissão do cartão | 536 |
| clientes com primeiro resgate na data de corte ou depois | 44953 |
| clientes com idade fora de 14 a 100 anos | 1779 |

## 04_valores

| verificacao | valor |
|---|---|
| transações com purchase_sum zero | 567 |
| transações com purchase_sum negativo | 0 |
| itens com quantidade zero ou negativa | 2,707,278 |
| itens com valor (trn_sum_from_iss) negativo | 0 |
| itens com quantidade acima de 100 | 180 |
| transações com soma dos itens diferente de purchase_sum em mais de 1% | 1,391,228 |
| purchase_sum: percentil 0,1% | 6.59 |
| purchase_sum: mediana | 282 |
| purchase_sum: percentil 99,9% | 4,471.954 |
| purchase_sum: máximo | 35,149.04 |
| transações acima do percentil 99,9% | 8,046 |
| pontos gastos positivos (deveriam ser <= 0) | 0 |

## 05_distribuicao

| ordem | distribuicao | estatistica | valor |
|---|---|---|---|
| 1 | transações por cliente | p10 | 4 |
| 2 | transações por cliente | mediana | 15 |
| 3 | transações por cliente | p90 | 42 |
| 4 | transações por cliente | p99 | 85 |
| 5 | transações por cliente | máximo | 320 |
| 6 | transações por loja | lojas | 13,882 |
| 7 | transações por loja | mediana | 517 |
| 8 | transações por loja | máximo | 2,956 |
| 11 | transações por dia da semana | Monday | 1,225,654 |
| 12 | transações por dia da semana | Tuesday | 1,046,744 |
| 13 | transações por dia da semana | Wednesday | 1,094,241 |
| 14 | transações por dia da semana | Thursday | 1,188,604 |
| 15 | transações por dia da semana | Friday | 1,244,880 |
| 16 | transações por dia da semana | Saturday | 1,160,554 |
| 17 | transações por dia da semana | Sunday | 1,084,524 |
