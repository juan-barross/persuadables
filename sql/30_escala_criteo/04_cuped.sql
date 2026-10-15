WITH base AS (
    SELECT treatment, COUNT(*) AS n, SUM(visit) AS sy, SUM(visit * visit) AS syy
    FROM criteo
    GROUP BY treatment
),

soma_x AS (
    UNPIVOT (SELECT treatment, SUM(COLUMNS('^f[0-9]+$')) FROM criteo GROUP BY treatment)
    ON COLUMNS('^f[0-9]+$')
    INTO NAME covariavel VALUE sx
),

soma_xx AS (
    UNPIVOT (
        SELECT treatment, SUM(COLUMNS('^f[0-9]+$') * COLUMNS('^f[0-9]+$'))
        FROM criteo
        GROUP BY treatment
    )
    ON COLUMNS('^f[0-9]+$')
    INTO NAME covariavel VALUE sxx
),

soma_xy AS (
    UNPIVOT (
        SELECT treatment, SUM(COLUMNS('^f[0-9]+$') * visit) FROM criteo GROUP BY treatment
    )
    ON COLUMNS('^f[0-9]+$')
    INTO NAME covariavel VALUE sxy
),

momentos AS (
    SELECT b.treatment, x.covariavel, b.n, b.sy, b.syy, x.sx, xx.sxx, xy.sxy
    FROM base AS b
    INNER JOIN soma_x AS x ON b.treatment = x.treatment
    INNER JOIN soma_xx AS xx ON x.treatment = xx.treatment AND x.covariavel = xx.covariavel
    INNER JOIN soma_xy AS xy ON x.treatment = xy.treatment AND x.covariavel = xy.covariavel
),

juntos AS (
    SELECT
        covariavel,
        (SUM(sxy) - SUM(sx) * SUM(sy) / SUM(n))
        / (SUM(sxx) - SUM(sx) * SUM(sx) / SUM(n)) AS theta,
        (SUM(sxy) - SUM(sx) * SUM(sy) / SUM(n))
        / SQRT(
            (SUM(sxx) - SUM(sx) * SUM(sx) / SUM(n)) * (SUM(syy) - SUM(sy) * SUM(sy) / SUM(n))
        ) AS rho,
        SUM(sx) / SUM(n) AS media_x
    FROM momentos
    GROUP BY covariavel
),

por_braco AS (
    SELECT
        m.covariavel,
        m.treatment,
        m.n,
        m.sy / m.n AS media_y,
        (m.syy - m.sy * m.sy / m.n) / (m.n - 1) AS var_y,
        m.sy / m.n - j.theta * (m.sx / m.n - j.media_x) AS media_aj,
        (m.syy - m.sy * m.sy / m.n) / (m.n - 1)
        + j.theta * j.theta * (m.sxx - m.sx * m.sx / m.n) / (m.n - 1)
        - 2 * j.theta * (m.sxy - m.sx * m.sy / m.n) / (m.n - 1) AS var_aj
    FROM momentos AS m
    INNER JOIN juntos AS j ON m.covariavel = j.covariavel
),

efeito AS (
    SELECT
        covariavel,
        MAX(media_y) FILTER (WHERE treatment = 1)
        - MAX(media_y) FILTER (WHERE treatment = 0) AS dif_bruta,
        SQRT(SUM(var_y / n)) AS ep_bruto,
        MAX(media_aj) FILTER (WHERE treatment = 1)
        - MAX(media_aj) FILTER (WHERE treatment = 0) AS dif_aj,
        SQRT(SUM(var_aj / n)) AS ep_aj
    FROM por_braco
    GROUP BY covariavel
)

SELECT
    e.covariavel,
    j.theta,
    j.rho * j.rho AS rho2,
    1 - POW(e.ep_aj / e.ep_bruto, 2) AS reducao_variancia,
    1 - e.ep_aj / e.ep_bruto AS reducao_largura_ic,
    e.dif_bruta * 100 AS efeito_bruto_pp,
    e.dif_aj * 100 AS efeito_cuped_pp,
    (e.dif_aj - 1.959964 * e.ep_aj) * 100 AS ic_inf_cuped_pp,
    (e.dif_aj + 1.959964 * e.ep_aj) * 100 AS ic_sup_cuped_pp
FROM efeito AS e
INNER JOIN juntos AS j ON e.covariavel = j.covariavel
ORDER BY reducao_variancia DESC;
