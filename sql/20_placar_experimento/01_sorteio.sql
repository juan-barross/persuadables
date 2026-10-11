-- Sorteio: quantos caíram em cada braço e o qui-quadrado contra 50/50.
-- Com uma categoria de 1 grau de liberdade, χ² = (n_t - n/2)² / (n/2) + (n_c - n/2)² / (n/2).
WITH bracos AS (
    SELECT
        COUNT(*) FILTER (WHERE treatment_flg = 1) AS n_tratamento,
        COUNT(*) FILTER (WHERE treatment_flg = 0) AS n_controle,
        COUNT(*) AS n
    FROM perfil_cliente
)

SELECT
    n_tratamento,
    n_controle,
    n_tratamento / n AS prop_tratamento,
    POW(n_tratamento - n / 2, 2) / (n / 2) + POW(n_controle - n / 2, 2) / (n / 2) AS qui2
FROM bracos;
