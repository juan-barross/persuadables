-- Como as compras se espalham por cliente, dia da semana e loja.
WITH transacoes AS (
    SELECT
        transaction_id,
        ANY_VALUE(client_id) AS client_id,
        ANY_VALUE(store_id) AS store_id,
        ANY_VALUE(transaction_datetime) AS quando
    FROM purchases
    GROUP BY transaction_id
),

por_cliente AS (
    SELECT client_id, COUNT(*) AS n FROM transacoes GROUP BY client_id
),

por_loja AS (
    SELECT store_id, COUNT(*) AS n FROM transacoes GROUP BY store_id
),

por_dia AS (
    SELECT ISODOW(quando) AS dia, DAYNAME(quando) AS nome, COUNT(*) AS n
    FROM transacoes
    GROUP BY 1, 2
)

SELECT 1 AS ordem, 'transações por cliente' AS distribuicao, 'p10' AS estatistica,
    QUANTILE_CONT(n, 0.1) AS valor FROM por_cliente
UNION ALL SELECT 2, 'transações por cliente', 'mediana', QUANTILE_CONT(n, 0.5) FROM por_cliente
UNION ALL SELECT 3, 'transações por cliente', 'p90', QUANTILE_CONT(n, 0.9) FROM por_cliente
UNION ALL SELECT 4, 'transações por cliente', 'p99', QUANTILE_CONT(n, 0.99) FROM por_cliente
UNION ALL SELECT 5, 'transações por cliente', 'máximo', MAX(n) FROM por_cliente
UNION ALL SELECT 6, 'transações por loja', 'lojas', COUNT(*) FROM por_loja
UNION ALL SELECT 7, 'transações por loja', 'mediana', QUANTILE_CONT(n, 0.5) FROM por_loja
UNION ALL SELECT 8, 'transações por loja', 'máximo', MAX(n) FROM por_loja
UNION ALL SELECT 10 + dia, 'transações por dia da semana', nome, n FROM por_dia
ORDER BY ordem;
