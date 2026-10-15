WITH longo AS (
    UNPIVOT (SELECT treatment, COLUMNS('^f[0-9]+$') FROM criteo)
    ON COLUMNS('^f[0-9]+$')
    INTO NAME variavel VALUE valor
),

por_braco AS (
    SELECT
        variavel,
        AVG(valor) FILTER (WHERE treatment = 1) AS media_tratamento,
        AVG(valor) FILTER (WHERE treatment = 0) AS media_controle,
        VAR_SAMP(valor) FILTER (WHERE treatment = 1) AS var_tratamento,
        VAR_SAMP(valor) FILTER (WHERE treatment = 0) AS var_controle
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
ORDER BY ABS(smd) DESC;
