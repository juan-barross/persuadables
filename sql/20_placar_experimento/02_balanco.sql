-- Balanço: diferença média padronizada (SMD) de cada variável do perfil entre os braços.
-- UNPIVOT transforma as colunas em linhas (variavel, valor) para calcular tudo de uma vez.
-- Regra usual: |SMD| < 0,1 é balanço bom.
WITH numericas AS (
    SELECT
        treatment_flg,
        COLUMNS(* EXCLUDE (client_id, target, treatment_flg))::DOUBLE
    FROM perfil_cliente
),

longo AS (
    UNPIVOT numericas
    ON COLUMNS(* EXCLUDE (treatment_flg))
    INTO NAME variavel VALUE valor
),

por_braco AS (
    SELECT
        variavel,
        AVG(valor) FILTER (WHERE treatment_flg = 1) AS media_tratamento,
        AVG(valor) FILTER (WHERE treatment_flg = 0) AS media_controle,
        VAR_SAMP(valor) FILTER (WHERE treatment_flg = 1) AS var_tratamento,
        VAR_SAMP(valor) FILTER (WHERE treatment_flg = 0) AS var_controle
    FROM longo
    GROUP BY variavel
)

SELECT
    variavel,
    media_tratamento,
    media_controle,
    (media_tratamento - media_controle)
    / NULLIF(SQRT((var_tratamento + var_controle) / 2), 0) AS smd
FROM por_braco
ORDER BY ABS(smd) DESC NULLS LAST;
