# ADR 0004: grão da transação e campos do cadastro posteriores ao corte

**Status:** aceita

## Contexto

A auditoria (`reports/auditoria.md`) achou três armadilhas para o perfil:

1. `purchases` tem uma linha por **item**, e `purchase_sum` é o valor da **transação**
   repetido em cada item. `SUM(purchase_sum)` direto infla o gasto pelo número de itens.
2. 28 `transaction_id` aparecem com dois clientes, duas lojas e dois horários: colisão
   do hash usado para anonimizar.
3. 44.953 clientes têm `first_redeem_date` (primeiro resgate de pontos) na data de corte
   ou depois. Usar a data como está é olhar para o futuro, e o resgate pode ter sido
   motivado pela própria campanha.

E duas que não são erro:

4. 2,7 milhões de itens têm `product_quantity = 0` com valor positivo: produtos vendidos
   por peso. Quantidade não entra no perfil.
5. Em 17% das transações a soma de `trn_sum_from_iss` dos itens difere de `purchase_sum`
   em mais de 1%, e somar `trn_sum_from_red` não explica. O valor da transação é
   `purchase_sum`.

## Decisão

- O primeiro passo do perfil (`sql/10_perfil_cliente/01_transacoes.sql`) colapsa
  `purchases` para uma linha por `(client_id, transaction_id)`, já filtrando
  `transaction_datetime < data_de_corte`. Todas as variáveis saem dessa tabela.
- `first_redeem_date >= data_de_corte` vira nulo, e "já resgatou antes do corte" vira a
  variável de fidelidade.
- Idades fora de 14 a 100 anos viram nulo (1.779 clientes).
