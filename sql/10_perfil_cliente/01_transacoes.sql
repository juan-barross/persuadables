-- Grão da transação: uma linha por (client_id, transaction_id), só antes do corte.
-- purchase_sum e os pontos são da transação e se repetem em cada item (ADR 0004),
-- por isso ANY_VALUE e não SUM. Só clientes do experimento entram.
CREATE OR REPLACE TABLE transacoes AS
SELECT
    p.client_id,
    p.transaction_id,
    ANY_VALUE(p.transaction_datetime) AS quando,
    ANY_VALUE(p.store_id) AS loja,
    ANY_VALUE(p.purchase_sum) AS valor,
    ANY_VALUE(p.regular_points_received + p.express_points_received) AS pontos_recebidos,
    -ANY_VALUE(p.regular_points_spent + p.express_points_spent) AS pontos_gastos,
    COUNT(*) AS itens
FROM purchases AS p
SEMI JOIN uplift_train AS u ON p.client_id = u.client_id
WHERE p.transaction_datetime < GETVARIABLE('data_de_corte')
GROUP BY p.client_id, p.transaction_id;
