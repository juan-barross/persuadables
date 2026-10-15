# Modelos de uplift

Gerado por `campanha uplift`. Divisão estratificada por tratamento × desfecho, semente
{semente}: treino {n_treino:,}, validação {n_validacao:,}, teste {n_teste:,}. Todos os modelos usam
LightGBM com os mesmos hiperparâmetros e as variáveis do perfil em SQL. O modelo escolhido
é o de maior AUUC na **validação** (`{escolhido}`); os números abaixo são do
**teste**, que nenhum modelo viu.

## Placar dos modelos (teste)

{tabela_metricas}

- `auuc` e `qini_auc`: área sob a curva de uplift e sob a curva Qini, normalizadas pelo
  sklift (quanto maior, melhor; 0 = aleatório).
- `uplift_top30_pp`: diferença de taxa de compra entre tratados e controle dentro dos
  30% de maior score. Efeito médio no teste: {efeito_medio_pp:.2f} p.p.
- `captura_top30`: fração das compras incrementais da base inteira que já está nos 30%
  de maior score.

**Leitura:** o `{escolhido}` encontra nos 30% de maior score um efeito de
{top30_escolhido_pp:.1f} p.p., contra {top30_propensao_pp:.1f} p.p. nos 30% que a
propensão escolhe.

![curva Qini](figuras/curva_qini.png)

## Uplift observado por decil de score (teste)

Decil 1 = maior score. Se o modelo funciona, o uplift observado cai do decil 1 ao 10.

| decil | uplift `{escolhido}` (p.p.) | uplift propensão (p.p.) | taxa do controle, propensão |
|---|---:|---:|---:|
{linhas_por_decil}

## Quem é influenciado

Mediana das variáveis do perfil nos 20% com maior uplift previsto pelo `{escolhido}`
contra os 20% com menor, no teste (valores em rublos):

{tabela_influenciados}

Nos 20% de maior uplift a campanha mudou a compra em {topo[uplift_observado_pp]:+.1f} p.p.
(IC [{topo[ic_inf_pp]:.1f}; {topo[ic_sup_pp]:.1f}]); nos 20% de menor, em
{base[uplift_observado_pp]:+.1f} p.p. (IC [{base[ic_inf_pp]:.1f}; {base[ic_sup_pp]:.1f}]).
Mediana dos mais influenciados contra os menos: {topo[n_transacoes]:.0f} contra
{base[n_transacoes]:.0f} transações, {topo[gasto_total]:,.0f} contra
{base[gasto_total]:,.0f} rublos gastos no período, {topo[dias_desde_ultima]:.1f} contra
{base[dias_desde_ultima]:.1f} dias desde a última compra, idade de {topo[idade]:.0f}
contra {base[idade]:.0f} anos. Sem a campanha,
{topo[taxa_controle]:.0%} deles comprariam, contra {base[taxa_controle]:.0%} no grupo
de menor uplift.
