SELECT 'primeira compra' AS verificacao, CAST(MIN(transaction_datetime) AS VARCHAR) AS valor
FROM purchases
UNION ALL
SELECT 'última compra', CAST(MAX(transaction_datetime) AS VARCHAR) FROM purchases
UNION ALL
SELECT 'data de corte usada', CAST(GETVARIABLE('data_de_corte') AS VARCHAR)
UNION ALL
SELECT
    'itens de compra na data de corte ou depois (vazamento em potencial)',
    CAST(COUNT(*) AS VARCHAR)
FROM purchases
WHERE transaction_datetime >= GETVARIABLE('data_de_corte')
UNION ALL
SELECT 'itens de compra antes de 2000 ou sem data', CAST(COUNT(*) AS VARCHAR)
FROM purchases
WHERE transaction_datetime IS NULL OR transaction_datetime < TIMESTAMP '2000-01-01'
UNION ALL
SELECT 'clientes com cartão emitido na data de corte ou depois', CAST(COUNT(*) AS VARCHAR)
FROM clients
WHERE first_issue_date >= GETVARIABLE('data_de_corte')
UNION ALL
SELECT 'clientes com primeiro resgate antes da emissão do cartão', CAST(COUNT(*) AS VARCHAR)
FROM clients
WHERE first_redeem_date < first_issue_date
UNION ALL
SELECT 'clientes com primeiro resgate na data de corte ou depois', CAST(COUNT(*) AS VARCHAR)
FROM clients
WHERE first_redeem_date >= GETVARIABLE('data_de_corte')
UNION ALL
SELECT 'clientes com idade fora de 14 a 100 anos', CAST(COUNT(*) AS VARCHAR)
FROM clients
WHERE age NOT BETWEEN 14 AND 100;
