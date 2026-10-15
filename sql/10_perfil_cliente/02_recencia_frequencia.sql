CREATE OR REPLACE TABLE f_recencia AS
WITH intervalos AS (
    SELECT
        client_id,
        quando,
        DATE_DIFF(
            'hour', LAG(quando) OVER (PARTITION BY client_id ORDER BY quando), quando
        ) AS horas_desde_anterior
    FROM transacoes
)

SELECT
    client_id,
    COUNT(*) AS n_transacoes,
    DATE_DIFF('hour', MAX(quando), GETVARIABLE('data_de_corte')) / 24.0
        AS dias_desde_ultima,
    DATE_DIFF('hour', MIN(quando), GETVARIABLE('data_de_corte')) / 24.0
        AS dias_desde_primeira,
    AVG(horas_desde_anterior) / 24.0 AS intervalo_medio_dias,
    SQRT(
        (
            SUM(horas_desde_anterior * horas_desde_anterior)
            - SUM(horas_desde_anterior) * SUM(horas_desde_anterior) / COUNT(horas_desde_anterior)
        )
        / NULLIF(COUNT(horas_desde_anterior) - 1, 0)
    ) / 24.0 AS intervalo_desvio_dias,
    COUNT(*) FILTER (WHERE quando >= GETVARIABLE('data_de_corte') - INTERVAL 30 DAY)
        AS n_transacoes_30d,
    COUNT(DISTINCT CAST(quando AS DATE)) AS dias_com_compra
FROM intervalos
GROUP BY client_id;
