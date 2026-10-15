CREATE OR REPLACE TABLE perfil_cliente AS
WITH base AS (
    SELECT
        u.client_id,
        u.treatment_flg,
        u.target,
        COALESCE(r.n_transacoes, 0) AS n_transacoes,
        r.dias_desde_ultima,
        r.dias_desde_primeira,
        r.intervalo_medio_dias,
        r.intervalo_desvio_dias,
        COALESCE(r.n_transacoes_30d, 0) AS n_transacoes_30d,
        COALESCE(r.dias_com_compra, 0) AS dias_com_compra,
        COALESCE(v.gasto_total, 0) AS gasto_total,
        v.ticket_medio,
        v.ticket_mediano,
        v.ticket_maximo,
        v.itens_por_transacao,
        COALESCE(v.gasto_30d, 0) AS gasto_30d,
        COALESCE(v.gasto_60d, 0) AS gasto_60d,
        COALESCE(v.gasto_90d, 0) AS gasto_90d,
        COALESCE(t.gasto_mes_0, 0) AS gasto_mes_0,
        COALESCE(t.gasto_mes_1, 0) AS gasto_mes_1,
        COALESCE(t.variacao_ultimo_mes, 0) AS variacao_ultimo_mes,
        COALESCE(t.media_movel_3m_anterior, 0) AS media_movel_3m_anterior,
        t.razao_ultimo_vs_media,
        f.pontos_recebidos,
        f.pontos_gastos,
        f.prop_transacoes_com_resgate,
        f.ja_resgatou,
        f.dias_desde_emissao,
        f.dias_ate_primeiro_resgate,
        f.idade,
        f.genero_f,
        f.genero_desconhecido,
        COALESCE(d.lojas_distintas, 0) AS lojas_distintas,
        d.prop_loja_principal,
        COALESCE(d.produtos_distintos, 0) AS produtos_distintos
    FROM uplift_train AS u
    LEFT JOIN f_recencia AS r ON u.client_id = r.client_id
    LEFT JOIN f_valor AS v ON u.client_id = v.client_id
    LEFT JOIN f_tendencia AS t ON u.client_id = t.client_id
    LEFT JOIN f_fidelidade AS f ON u.client_id = f.client_id
    LEFT JOIN f_diversidade AS d ON u.client_id = d.client_id
)

SELECT
    *,
    NTILE(10) OVER (ORDER BY gasto_total, client_id) AS decil_gasto,
    NTILE(10) OVER (ORDER BY n_transacoes, client_id) AS decil_frequencia,
    NTILE(10) OVER (ORDER BY ticket_medio NULLS FIRST, client_id) AS decil_ticket,
    CASE WHEN dias_desde_ultima > 14 OR dias_desde_ultima IS NULL THEN 1 ELSE 0 END
        AS inativo_14d
FROM base
ORDER BY client_id;

SELECT
    (SELECT COUNT(*) FROM uplift_train) AS clientes_experimento,
    COUNT(*) AS linhas_perfil,
    COUNT(DISTINCT client_id) AS clientes_perfil,
    COUNT(*) FILTER (WHERE n_transacoes = 0) AS clientes_sem_compra_antes_do_corte,
    MAX(dias_desde_ultima) AS max_dias_desde_ultima,
    AVG(inativo_14d) AS prop_inativos_14d,
    AVG(ja_resgatou) AS prop_ja_resgatou,
    MEDIAN(gasto_total) AS mediana_gasto_total,
    MEDIAN(ticket_medio) AS mediana_ticket_medio
FROM perfil_cliente;
