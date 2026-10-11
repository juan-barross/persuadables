-- Efeito por segmento. O p-valor e a correção de Benjamini-Hochberg são feitos em
-- Python (stats.benjamini_hochberg), porque são muitos testes ao mesmo tempo.
-- A faixa de ticket histórico faz o papel possível da métrica de proteção (ADR 0002).
WITH segmentado AS (
    SELECT
        treatment_flg,
        target,
        CASE WHEN inativo_14d = 1 THEN 'sem comprar há mais de 14 dias'
            ELSE 'comprou nos últimos 14 dias' END AS recencia_14d,
        'Q' || NTILE(4) OVER (ORDER BY dias_desde_ultima, client_id)
        || ' (1 = mais recente)' AS quartil_recencia,
        'D' || LPAD(decil_gasto::VARCHAR, 2, '0') AS decil_gasto,
        'D' || LPAD(decil_frequencia::VARCHAR, 2, '0') AS decil_frequencia,
        'D' || LPAD(decil_ticket::VARCHAR, 2, '0') AS decil_ticket,
        CASE WHEN ja_resgatou = 1 THEN 'já resgatou pontos' ELSE 'nunca resgatou' END
            AS fidelidade
    FROM perfil_cliente
),

longo AS (
    UNPIVOT segmentado
    ON recencia_14d, quartil_recencia, decil_gasto, decil_frequencia, decil_ticket, fidelidade
    INTO NAME segmento VALUE nivel
),

contagens AS (
    SELECT
        segmento,
        nivel,
        COUNT(*) FILTER (WHERE treatment_flg = 1) AS n_t,
        COUNT(*) FILTER (WHERE treatment_flg = 0) AS n_c,
        AVG(target) FILTER (WHERE treatment_flg = 1) AS taxa_t,
        AVG(target) FILTER (WHERE treatment_flg = 0) AS taxa_c
    FROM longo
    GROUP BY segmento, nivel
)

SELECT
    segmento,
    nivel,
    n_t,
    n_c,
    taxa_t,
    taxa_c,
    (taxa_t - taxa_c) * 100 AS efeito_pp,
    SQRT(taxa_t * (1 - taxa_t) / n_t + taxa_c * (1 - taxa_c) / n_c) * 100 AS ep_pp,
    (taxa_t - taxa_c) / SQRT(taxa_t * (1 - taxa_t) / n_t + taxa_c * (1 - taxa_c) / n_c) AS z
FROM contagens
ORDER BY segmento, nivel;
