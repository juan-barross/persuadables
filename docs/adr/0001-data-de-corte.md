# ADR 0001: data de corte da campanha é 2019-03-19 00:00

**Status:** aceita

## Contexto

O perfil do cliente só pode usar o que se sabia antes da comunicação. Qualquer compra
feita depois dela pode ter sido causada pela própria campanha e contamina tanto o
balanço do experimento quanto o modelo de uplift.

A documentação do scikit-uplift diz que `purchases` traz o histórico "anterior à
comunicação", mas não dá a data. A auditoria (`sql/00_auditoria/03_datas.sql`) mostra:

- primeira compra em 2018-11-21 21:02, última em 2019-03-18 23:40;
- o último dia tem volume normal (cerca de 80 mil transações, igual aos dias anteriores),
  ou seja, a série é cortada, não vai minguando.

## Decisão

`DATA_DE_CORTE = 2019-03-19 00:00` em `src/persuadables/run_sql.py`, exposta ao SQL como
`getvariable('data_de_corte')`. Todo SQL do perfil filtra `transaction_datetime <
data_de_corte`, e campos de data do cadastro posteriores ao corte viram nulo
(ver ADR 0004).

## Consequências

- Na base real o filtro não remove nenhuma linha. O teste de vazamento por isso roda
  sobre uma amostra sintética com compras plantadas depois do corte; na base real ele
  serviria só como checagem de que nada mudou.
- Se a X5 publicasse o histórico pós-campanha, o mesmo filtro continuaria correto.
