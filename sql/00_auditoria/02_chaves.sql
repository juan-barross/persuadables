-- Integridade das chaves entre as três tabelas.
SELECT 'itens de compra sem cliente em clients' AS verificacao, COUNT(*) AS valor
FROM purchases AS p
WHERE NOT EXISTS (SELECT 1 FROM clients AS c WHERE c.client_id = p.client_id)
UNION ALL
SELECT 'clientes do experimento ausentes de clients', COUNT(*)
FROM uplift_train AS u
WHERE NOT EXISTS (SELECT 1 FROM clients AS c WHERE c.client_id = u.client_id)
UNION ALL
SELECT 'client_id repetido em clients', COUNT(*) - COUNT(DISTINCT client_id) FROM clients
UNION ALL
SELECT 'client_id repetido em uplift_train', COUNT(*) - COUNT(DISTINCT client_id)
FROM uplift_train
UNION ALL
SELECT 'treatment_flg fora de {0, 1}', COUNT(*) FILTER (WHERE treatment_flg NOT IN (0, 1))
FROM uplift_train
UNION ALL
SELECT 'target fora de {0, 1}', COUNT(*) FILTER (WHERE target NOT IN (0, 1)) FROM uplift_train
UNION ALL
-- Uma transação deveria ter um só cliente, uma só loja e um só horário.
-- Na X5 há 28 colisões do hash de transaction_id (2 clientes, 2 lojas, 2 horários):
-- por isso o grão da transação no perfil é (client_id, transaction_id).
SELECT 'transações com mais de um cliente, loja ou horário', COUNT(*)
FROM (
    SELECT transaction_id
    FROM purchases
    GROUP BY transaction_id
    HAVING
        COUNT(DISTINCT client_id) > 1
        OR COUNT(DISTINCT store_id) > 1
        OR COUNT(DISTINCT transaction_datetime) > 1
)
UNION ALL
-- purchase_sum é da transação e se repete em cada item: somar direto multiplica o gasto.
SELECT 'transações com purchase_sum diferente entre os itens', COUNT(*)
FROM (
    SELECT transaction_id
    FROM purchases
    GROUP BY transaction_id
    HAVING COUNT(DISTINCT purchase_sum) > 1
)
UNION ALL
SELECT 'itens repetidos (mesma transação e produto)', COUNT(*) - COUNT(DISTINCT (transaction_id, product_id))
FROM purchases;
