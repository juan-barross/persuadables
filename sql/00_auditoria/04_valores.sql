WITH transacoes AS (
    SELECT
        client_id,
        transaction_id,
        ANY_VALUE(purchase_sum) AS purchase_sum,
        SUM(trn_sum_from_iss) AS soma_itens,
        SUM(product_quantity) AS quantidade
    FROM purchases
    GROUP BY client_id, transaction_id
),

limites AS (
    SELECT
        QUANTILE_CONT(purchase_sum, 0.001) AS p001,
        QUANTILE_CONT(purchase_sum, 0.5) AS p50,
        QUANTILE_CONT(purchase_sum, 0.999) AS p999
    FROM transacoes
)

SELECT 'transações com purchase_sum zero' AS verificacao, COUNT(*)::DOUBLE AS valor
FROM transacoes WHERE purchase_sum = 0
UNION ALL
SELECT 'transações com purchase_sum negativo', COUNT(*) FROM transacoes WHERE purchase_sum < 0
UNION ALL
SELECT 'itens com quantidade zero ou negativa', COUNT(*)
FROM purchases WHERE product_quantity <= 0
UNION ALL
SELECT 'itens com valor (trn_sum_from_iss) negativo', COUNT(*)
FROM purchases WHERE trn_sum_from_iss < 0
UNION ALL
SELECT 'itens com quantidade acima de 100', COUNT(*)
FROM purchases WHERE product_quantity > 100
UNION ALL
SELECT 'transações com soma dos itens diferente de purchase_sum em mais de 1%', COUNT(*)
FROM transacoes
WHERE ABS(soma_itens - purchase_sum) > 0.01 * ABS(purchase_sum)
UNION ALL
SELECT 'purchase_sum: percentil 0,1%', p001 FROM limites
UNION ALL
SELECT 'purchase_sum: mediana', p50 FROM limites
UNION ALL
SELECT 'purchase_sum: percentil 99,9%', p999 FROM limites
UNION ALL
SELECT 'purchase_sum: máximo', MAX(purchase_sum) FROM transacoes
UNION ALL
SELECT 'transações acima do percentil 99,9%', COUNT(*)
FROM transacoes AS t CROSS JOIN limites AS l WHERE t.purchase_sum > l.p999
UNION ALL
SELECT 'pontos gastos positivos (deveriam ser <= 0)', COUNT(*)
FROM purchases WHERE regular_points_spent > 0 OR express_points_spent > 0;
