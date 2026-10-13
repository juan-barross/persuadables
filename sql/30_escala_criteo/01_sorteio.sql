-- Sorteio na Criteo: o tratamento é `treatment` (sorteado, 85% esperados), não `exposure`
-- (quem de fato viu o anúncio, que depende do comportamento do usuário).
WITH bracos AS (
    SELECT
        COUNT(*) FILTER (WHERE treatment = 1) AS n_tratamento,
        COUNT(*) FILTER (WHERE treatment = 0) AS n_controle,
        COUNT(*) AS n,
        AVG(exposure) FILTER (WHERE treatment = 1) AS exposicao_tratados,
        AVG(exposure) FILTER (WHERE treatment = 0) AS exposicao_controle
    FROM criteo
)

SELECT
    n,
    n_tratamento,
    n_controle,
    exposicao_tratados,
    exposicao_controle,
    n_tratamento / n AS prop_tratamento,
    POW(n_tratamento - 0.85 * n, 2) / (0.85 * n)
    + POW(n_controle - 0.15 * n, 2) / (0.15 * n) AS qui2_vs_85pct
FROM bracos;
