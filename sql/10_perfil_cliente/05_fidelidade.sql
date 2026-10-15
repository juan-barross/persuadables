CREATE OR REPLACE TABLE f_fidelidade AS
WITH pontos AS (
    SELECT
        client_id,
        SUM(pontos_recebidos) AS pontos_recebidos,
        SUM(pontos_gastos) AS pontos_gastos,
        AVG(CASE WHEN pontos_gastos > 0 THEN 1.0 ELSE 0.0 END) AS prop_transacoes_com_resgate
    FROM transacoes
    GROUP BY client_id
),

cadastro AS (
    SELECT
        client_id,
        CASE WHEN first_issue_date < GETVARIABLE('data_de_corte') THEN first_issue_date END
            AS emissao,
        CASE WHEN first_redeem_date < GETVARIABLE('data_de_corte') THEN first_redeem_date END
            AS resgate,
        CASE WHEN age BETWEEN 14 AND 100 THEN age END AS idade,
        gender
    FROM clients
)

SELECT
    u.client_id,
    COALESCE(p.pontos_recebidos, 0) AS pontos_recebidos,
    COALESCE(p.pontos_gastos, 0) AS pontos_gastos,
    COALESCE(p.prop_transacoes_com_resgate, 0) AS prop_transacoes_com_resgate,
    CASE WHEN c.resgate IS NOT NULL THEN 1 ELSE 0 END AS ja_resgatou,
    DATE_DIFF('day', c.emissao, GETVARIABLE('data_de_corte')) AS dias_desde_emissao,
    DATE_DIFF('day', c.emissao, c.resgate) AS dias_ate_primeiro_resgate,
    c.idade,
    CASE c.gender WHEN 'F' THEN 1 WHEN 'M' THEN 0 END AS genero_f,
    CASE WHEN c.gender = 'U' OR c.gender IS NULL THEN 1 ELSE 0 END AS genero_desconhecido
FROM uplift_train AS u
LEFT JOIN cadastro AS c ON u.client_id = c.client_id
LEFT JOIN pontos AS p ON u.client_id = p.client_id;
