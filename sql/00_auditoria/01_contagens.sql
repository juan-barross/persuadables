-- Tamanho de cada tabela e cobertura do experimento.
-- purchases tem uma linha por item; a transação é transaction_id.
WITH clientes_com_compra AS (
    SELECT DISTINCT client_id FROM purchases
)

SELECT 'linhas em clients' AS verificacao, COUNT(*) AS valor FROM clients
UNION ALL
SELECT 'linhas em uplift_train', COUNT(*) FROM uplift_train
UNION ALL
SELECT 'linhas em purchases (itens)', COUNT(*) FROM purchases
UNION ALL
SELECT 'transações distintas', COUNT(DISTINCT transaction_id) FROM purchases
UNION ALL
SELECT 'clientes distintos com compra', COUNT(*) FROM clientes_com_compra
UNION ALL
SELECT 'clientes do experimento sem nenhuma compra', COUNT(*)
FROM uplift_train AS u
WHERE NOT EXISTS (SELECT 1 FROM clientes_com_compra AS c WHERE c.client_id = u.client_id)
UNION ALL
SELECT 'clientes do experimento tratados', SUM(treatment_flg) FROM uplift_train
UNION ALL
SELECT 'clientes do experimento que compraram depois (target = 1)', SUM(target)
FROM uplift_train;
