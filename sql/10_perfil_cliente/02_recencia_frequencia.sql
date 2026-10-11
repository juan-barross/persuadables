-- Recência e frequência. Intervalo entre compras com LAG sobre as transações do cliente.
CREATE OR REPLACE TABLE f_recencia AS
WITH intervalos AS (
    SELECT
        client_id,
        quando,
        DATE_DIFF(
            'hour', LAG(quando) OVER (PARTITION BY client_id ORDER BY quando), quando
        ) / 24.0 AS dias_desde_anterior
    FROM transacoes
)

SELECT
    client_id,
    COUNT(*) AS n_transacoes,
    DATE_DIFF('hour', MAX(quando), getvariable('data_de_corte')) / 24.0
        AS dias_desde_ultima,
    DATE_DIFF('hour', MIN(quando), getvariable('data_de_corte')) / 24.0
        AS dias_desde_primeira,
    AVG(dias_desde_anterior) AS intervalo_medio_dias,
    STDDEV_SAMP(dias_desde_anterior) AS intervalo_desvio_dias,
    COUNT(*) FILTER (WHERE quando >= getvariable('data_de_corte') - INTERVAL 30 DAY)
        AS n_transacoes_30d,
    COUNT(DISTINCT CAST(quando AS DATE)) AS dias_com_compra
FROM intervalos
GROUP BY client_id;
