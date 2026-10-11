-- Tendência de gasto.
--
-- 1) gasto_mensal: mês do calendário com DATE_TRUNC e variação contra o mês anterior.
--    Bom para leitura, mas março/2019 tem só 18 dias e novembro/2018 só 10, então
--    comparar os dois últimos meses do calendário confunde queda com mês curto.
-- 2) f_tendencia: por isso as variáveis usam "meses móveis" de 30 dias que terminam
--    no corte (janela 0 = últimos 30 dias), com zero onde o cliente não comprou.
CREATE OR REPLACE TABLE gasto_mensal AS
WITH mensal AS (
    SELECT client_id, DATE_TRUNC('month', quando) AS mes, SUM(valor) AS gasto_mes
    FROM transacoes
    GROUP BY 1, 2
)

SELECT
    client_id,
    mes,
    gasto_mes,
    gasto_mes - LAG(gasto_mes) OVER (PARTITION BY client_id ORDER BY mes) AS variacao
FROM mensal;

CREATE OR REPLACE TABLE f_tendencia AS
WITH janelas AS (
    SELECT
        client_id,
        FLOOR(DATE_DIFF('hour', quando, getvariable('data_de_corte')) / (24.0 * 30))::INT
            AS janela,
        SUM(valor) AS gasto
    FROM transacoes
    GROUP BY 1, 2
),

grade AS (
    -- Todo cliente tem as janelas 0 a 3, mesmo sem compra nelas.
    SELECT c.client_id, j.janela
    FROM (SELECT DISTINCT client_id FROM transacoes) AS c
    CROSS JOIN RANGE(4) AS j (janela)
),

serie AS (
    SELECT
        g.client_id,
        g.janela,
        COALESCE(j.gasto, 0) AS gasto
    FROM grade AS g
    LEFT JOIN janelas AS j ON g.client_id = j.client_id AND g.janela = j.janela
),

com_janelas AS (
    SELECT
        client_id,
        janela,
        gasto,
        -- janela maior = mais antiga: em ordem decrescente, o LAG é o mês anterior
        gasto - LAG(gasto) OVER (PARTITION BY client_id ORDER BY janela DESC) AS variacao,
        -- média da própria janela e das duas mais antigas
        AVG(gasto) OVER (
            PARTITION BY client_id ORDER BY janela
            ROWS BETWEEN CURRENT ROW AND 2 FOLLOWING
        ) AS media_movel_3
    FROM serie
)

SELECT
    client_id,
    MAX(gasto) FILTER (WHERE janela = 0) AS gasto_mes_0,
    MAX(gasto) FILTER (WHERE janela = 1) AS gasto_mes_1,
    MAX(variacao) FILTER (WHERE janela = 0) AS variacao_ultimo_mes,
    MAX(media_movel_3) FILTER (WHERE janela = 1) AS media_movel_3m_anterior,
    MAX(gasto) FILTER (WHERE janela = 0)
    / NULLIF(MAX(media_movel_3) FILTER (WHERE janela = 1), 0) AS razao_ultimo_vs_media
FROM com_janelas
GROUP BY client_id;
