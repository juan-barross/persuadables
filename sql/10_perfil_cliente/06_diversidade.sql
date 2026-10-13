-- Diversidade: lojas e produtos diferentes, e o peso da loja preferida.
-- Produto é atributo do item, então aqui é preciso voltar a purchases (com o corte).
CREATE OR REPLACE TABLE f_diversidade AS
WITH produtos AS (
    SELECT p.client_id, COUNT(DISTINCT p.product_id) AS produtos_distintos
    FROM purchases AS p
    SEMI JOIN uplift_train AS u ON p.client_id = u.client_id
    WHERE p.transaction_datetime < GETVARIABLE('data_de_corte')
    GROUP BY p.client_id
),

por_loja AS (
    SELECT client_id, loja, COUNT(*) AS n
    FROM transacoes
    GROUP BY client_id, loja
),

lojas AS (
    SELECT
        client_id,
        COUNT(*) AS lojas_distintas,
        MAX(n) / SUM(n) AS prop_loja_principal
    FROM por_loja
    GROUP BY client_id
)

SELECT l.client_id, l.lojas_distintas, l.prop_loja_principal, p.produtos_distintos
FROM lojas AS l
LEFT JOIN produtos AS p ON l.client_id = p.client_id;
