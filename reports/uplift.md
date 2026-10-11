# Modelos de uplift

Gerado por `campanha uplift`. Divisão estratificada por tratamento × desfecho, semente
42: treino 120,023, validação 40,008, teste 40,008. Todos os modelos usam
LightGBM com os mesmos hiperparâmetros e as variáveis do perfil em SQL. O modelo escolhido
é o de maior AUUC na **validação** (`S-learner`); os números abaixo são do
**teste**, que nenhum modelo viu.

## Placar dos modelos (teste)

| modelo | auuc | qini_auc | uplift_top10_pp | uplift_top30_pp | captura_top30 |
|---|---|---|---|---|---|
| X-learner | 0.0163 | 0.0104 | 10.3663 | 5.5708 | 0.4963 |
| S-learner | 0.0158 | 0.0102 | 10.1981 | 5.6496 | 0.5101 |
| class transformation | 0.0088 | 0.0056 | 4.6231 | 4.6289 | 0.4117 |
| T-learner | 0.0083 | 0.0054 | 8.9011 | 4.2119 | 0.3768 |
| propensão | -0.0071 | -0.0045 | 1.1782 | 1.62 | 0.1462 |

- `auuc` e `qini_auc`: área sob a curva de uplift e sob a curva Qini, normalizadas pelo
  sklift (quanto maior, melhor; 0 = aleatório).
- `uplift_top30_pp`: diferença de taxa de compra entre tratados e controle dentro dos
  30% de maior score. Efeito médio no teste: 3.32 p.p.
- `captura_top30`: fração das compras incrementais da base inteira que já está nos 30%
  de maior score.

**Leitura:** o `S-learner` encontra nos 30% de maior score um efeito de
5.6 p.p., contra 1.6 p.p. nos 30% que a
propensão escolhe.

![curva Qini](figuras/curva_qini.png)

## Uplift observado por decil de score (teste)

Decil 1 = maior score. Se o modelo funciona, o uplift observado cai do decil 1 ao 10.

| decil | uplift `S-learner` (p.p.) | uplift propensão (p.p.) | taxa do controle, propensão |
|---|---:|---:|---:|
| 1 | +10.2 [7.1; 13.3] | +1.2 [-0.0; 2.4] | 95% |
| 2 | +3.4 [0.3; 6.5] | +0.5 [-1.5; 2.4] | 89% |
| 3 | +3.3 [0.2; 6.4] | +2.9 [0.6; 5.3] | 81% |
| 4 | -0.1 [-3.2; 3.0] | +2.6 [-0.0; 5.3] | 73% |
| 5 | +3.3 [0.2; 6.3] | +6.7 [3.7; 9.6] | 63% |
| 6 | +4.6 [1.6; 7.6] | +4.8 [1.8; 7.9] | 57% |
| 7 | +1.5 [-1.4; 4.5] | +2.2 [-0.9; 5.3] | 50% |
| 8 | +2.9 [0.1; 5.7] | +5.7 [2.7; 8.8] | 40% |
| 9 | +2.0 [-0.6; 4.6] | +3.1 [0.2; 6.1] | 33% |
| 10 | +1.6 [-1.2; 4.4] | +2.7 [0.1; 5.3] | 22% |

## Quem é influenciado

Mediana das variáveis do perfil nos 20% com maior uplift previsto pelo `S-learner`
contra os 20% com menor, no teste (valores em rublos):

| grupo | n | taxa_controle | uplift_observado_pp | ic_inf_pp | ic_sup_pp | gasto_total | ticket_medio | n_transacoes | dias_desde_ultima | gasto_30d | intervalo_medio_dias | ja_resgatou | prop_transacoes_com_resgate | lojas_distintas | idade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20% maior uplift | 8,001 | 0.46 | 6.8 | 4.62 | 8.99 | 2,761.54 | 294 | 9 | 7.42 | 755.12 | 9.34 | 1 | 0.07 | 2 | 58 |
| 20% menor uplift | 8,001 | 0.74 | 1.76 | -0.13 | 3.65 | 13,127.6 | 438.88 | 32 | 2.42 | 3,572.17 | 3.26 | 1 | 0.03 | 3 | 39 |
| todos | 40,008 | 0.6 | 3.32 | 2.37 | 4.27 | 6,110.61 | 394.85 | 15 | 4.42 | 1,804 | 6.17 | 1 | 0.04 | 2 | 45 |

Nos 20% de maior uplift a campanha mudou a compra em +6.8 p.p.
(IC [4.6; 9.0]); nos 20% de menor, em
+1.8 p.p. (IC [-0.1; 3.6]).
Mediana dos mais influenciados contra os menos: 9 contra
32 transações, 2,762 contra
13,128 rublos gastos no período, 7.4 contra
2.4 dias desde a última compra, idade de 58
contra 39 anos. Sem a campanha,
46% deles comprariam, contra 74% no grupo
de menor uplift.
