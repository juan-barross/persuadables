-- Valor: ticket e gasto em janelas que terminam no corte.
CREATE OR REPLACE TABLE f_valor AS
SELECT
    client_id,
    SUM(valor) AS gasto_total,
    AVG(valor) AS ticket_medio,
    MEDIAN(valor) AS ticket_mediano,
    MAX(valor) AS ticket_maximo,
    AVG(itens) AS itens_por_transacao,
    COALESCE(SUM(valor) FILTER (
        WHERE quando >= GETVARIABLE('data_de_corte') - INTERVAL 30 DAY
    ), 0) AS gasto_30d,
    COALESCE(SUM(valor) FILTER (
        WHERE quando >= GETVARIABLE('data_de_corte') - INTERVAL 60 DAY
    ), 0) AS gasto_60d,
    COALESCE(SUM(valor) FILTER (
        WHERE quando >= GETVARIABLE('data_de_corte') - INTERVAL 90 DAY
    ), 0) AS gasto_90d
FROM transacoes
GROUP BY client_id;
