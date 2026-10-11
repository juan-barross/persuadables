-- Efeito médio (intenção de tratar) em visita e conversão, com IC 95% de Wald.
WITH longo AS (
    UNPIVOT (SELECT treatment, visit, conversion FROM criteo)
    ON visit, conversion
    INTO NAME desfecho VALUE y
),

bracos AS (
    SELECT
        desfecho,
        COUNT(*) FILTER (WHERE treatment = 1) AS n_t,
        COUNT(*) FILTER (WHERE treatment = 0) AS n_c,
        AVG(y) FILTER (WHERE treatment = 1) AS taxa_t,
        AVG(y) FILTER (WHERE treatment = 0) AS taxa_c
    FROM longo
    GROUP BY desfecho
),

efeito AS (
    SELECT
        *,
        taxa_t - taxa_c AS dif,
        SQRT(taxa_t * (1 - taxa_t) / n_t + taxa_c * (1 - taxa_c) / n_c) AS ep
    FROM bracos
)

SELECT
    desfecho,
    taxa_t,
    taxa_c,
    dif * 100 AS efeito_pp,
    (dif - 1.959964 * ep) * 100 AS ic_inf_pp,
    (dif + 1.959964 * ep) * 100 AS ic_sup_pp,
    dif / taxa_c * 100 AS efeito_relativo_pct,
    dif / ep AS z
FROM efeito
ORDER BY desfecho DESC;
