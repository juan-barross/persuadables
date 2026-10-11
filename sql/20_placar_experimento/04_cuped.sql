-- CUPED em SQL, para várias covariáveis pré-campanha de uma vez.
-- θ = cov(y, x) / var(x) juntando os braços; y_aj = y - θ (x - média(x)).
-- A redução da variância do estimador deve ficar perto de ρ(y, x)².
WITH longo AS (
    UNPIVOT (
        SELECT
            client_id,
            treatment_flg,
            target,
            n_transacoes::DOUBLE AS n_transacoes,
            n_transacoes_30d::DOUBLE AS n_transacoes_30d,
            dias_com_compra::DOUBLE AS dias_com_compra,
            gasto_total,
            gasto_30d,
            COALESCE(dias_desde_ultima, 0) AS dias_desde_ultima,
            COALESCE(intervalo_medio_dias, 0) AS intervalo_medio_dias
        FROM perfil_cliente
    )
    ON n_transacoes, n_transacoes_30d, dias_com_compra, gasto_total, gasto_30d,
    dias_desde_ultima, intervalo_medio_dias
    INTO NAME covariavel VALUE x
),

theta AS (
    SELECT
        covariavel,
        COVAR_SAMP(target, x) / VAR_SAMP(x) AS theta,
        CORR(target, x) AS rho,
        AVG(x) AS media_x
    FROM longo
    GROUP BY covariavel
),

ajustado AS (
    SELECT
        l.covariavel,
        l.treatment_flg,
        l.target AS y,
        l.target - t.theta * (l.x - t.media_x) AS y_aj
    FROM longo AS l
    INNER JOIN theta AS t ON l.covariavel = t.covariavel
),

por_braco AS (
    SELECT
        covariavel,
        AVG(y) FILTER (WHERE treatment_flg = 1) - AVG(y) FILTER (WHERE treatment_flg = 0)
            AS dif_bruta,
        SQRT(
            VAR_SAMP(y) FILTER (WHERE treatment_flg = 1)
            / COUNT(*) FILTER (WHERE treatment_flg = 1)
            + VAR_SAMP(y) FILTER (WHERE treatment_flg = 0)
            / COUNT(*) FILTER (WHERE treatment_flg = 0)
        ) AS ep_bruto,
        AVG(y_aj) FILTER (WHERE treatment_flg = 1)
        - AVG(y_aj) FILTER (WHERE treatment_flg = 0) AS dif_aj,
        SQRT(
            VAR_SAMP(y_aj) FILTER (WHERE treatment_flg = 1)
            / COUNT(*) FILTER (WHERE treatment_flg = 1)
            + VAR_SAMP(y_aj) FILTER (WHERE treatment_flg = 0)
            / COUNT(*) FILTER (WHERE treatment_flg = 0)
        ) AS ep_aj
    FROM ajustado
    GROUP BY covariavel
)

SELECT
    b.covariavel,
    t.theta,
    t.rho,
    t.rho * t.rho AS rho2,
    1 - POW(b.ep_aj / b.ep_bruto, 2) AS reducao_variancia,
    1 - b.ep_aj / b.ep_bruto AS reducao_largura_ic,
    b.dif_bruta * 100 AS efeito_bruto_pp,
    b.dif_aj * 100 AS efeito_cuped_pp,
    (b.dif_aj - 1.959964 * b.ep_aj) * 100 AS ic_inf_cuped_pp,
    (b.dif_aj + 1.959964 * b.ep_aj) * 100 AS ic_sup_cuped_pp
FROM por_braco AS b
INNER JOIN theta AS t ON b.covariavel = t.covariavel
ORDER BY reducao_variancia DESC;
