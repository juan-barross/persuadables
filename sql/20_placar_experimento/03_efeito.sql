WITH bracos AS (
    SELECT
        COUNT(*) FILTER (WHERE treatment_flg = 1) AS n_t,
        COUNT(*) FILTER (WHERE treatment_flg = 0) AS n_c,
        AVG(target) FILTER (WHERE treatment_flg = 1) AS taxa_t,
        AVG(target) FILTER (WHERE treatment_flg = 0) AS taxa_c
    FROM perfil_cliente
),

efeito AS (
    SELECT
        *,
        taxa_t - taxa_c AS dif,
        SQRT(taxa_t * (1 - taxa_t) / n_t + taxa_c * (1 - taxa_c) / n_c) AS ep
    FROM bracos
)

SELECT
    n_t,
    n_c,
    taxa_t,
    taxa_c,
    dif * 100 AS efeito_pp,
    (dif - 1.959964 * ep) * 100 AS ic_inf_pp,
    (dif + 1.959964 * ep) * 100 AS ic_sup_pp,
    dif / taxa_c * 100 AS efeito_relativo_pct,
    dif * n_t AS compras_incrementais,
    (dif - 1.959964 * ep) * n_t AS compras_incrementais_inf,
    (dif + 1.959964 * ep) * n_t AS compras_incrementais_sup,
    dif / ep AS z
FROM efeito;
