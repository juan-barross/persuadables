# Placar do experimento

Gerado por `persuadables placar` a partir de `sql/20_placar_experimento/`. Desfecho: `target`
(comprou depois da comunicação). Tratados: {n_t:,}. Controle: {n_c:,}.

## 1. O sorteio está são?

| checagem | resultado | leitura |
|---|---|---|
| proporção de tratados | {prop_tratamento:.4f} | esperado 0,5 |
| qui-quadrado (SRM) | p = {p_srm:.3f} | sem sinal de sorteio torto |
| maior \|SMD\| entre {n_variaveis_balanco} variáveis | {max_abs_smd:.4f} | tudo abaixo de 0,1: braços comparáveis |

## 2. Efeito médio

| | controle | tratamento | diferença |
|---|---:|---:|---:|
| taxa de compra | {taxa_c:.2%} | {taxa_t:.2%} | **{efeito_pp:+.2f} p.p.** |

- IC 95% analítico (Wald, no SQL): [{ic_inf_pp:.2f}; {ic_sup_pp:.2f}] p.p.
- IC 95% por bootstrap (5.000 reamostras): [{boot_inf_pp:.2f}; {boot_sup_pp:.2f}] p.p.
- p-valor: {p_valor:.1e}
- Relativo: {efeito_relativo_pct:+.1f}% sobre a taxa do controle.
- Em compras: cerca de **{compras_incrementais:,.0f} compradores a mais** entre
  {n_t:,} tratados. Como {taxa_c:.0%} comprariam de qualquer jeito, cerca de
  {compraria_sem_campanha:.0%} das compras dos tratados não foram causadas pela campanha.

## 3. Redução de variância (CUPED)

| método | covariáveis | redução da variância | IC encolhe | efeito (p.p.) | IC 95% |
|---|---|---:|---:|---:|---|
| sem ajuste | - | - | - | {efeito_pp:.2f} | [{ic_inf_pp:.2f}; {ic_sup_pp:.2f}] |
| CUPED (SQL) | `{cuped_sql_covariavel}` | {cuped_sql_reducao_variancia:.1%} | {cuped_sql_reducao_ic:.1%} | {cuped_sql_efeito_pp:.2f} | [{cuped_sql_ic_inf_pp:.2f}; {cuped_sql_ic_sup_pp:.2f}] |
| CUPED por regressão | {n_covariaveis} do perfil | {cuped_reg_reducao_variancia:.1%} | {cuped_reg_reducao_ic:.1%} | {cuped_reg_efeito_pp:.2f} | [{cuped_reg_ic_inf_pp:.2f}; {cuped_reg_ic_sup_pp:.2f}] |

A redução da variância bate com ρ² da covariável ({cuped_sql_rho2:.3f}), como a teoria prevê.
Ela é modesta porque o desfecho é binário: o histórico explica parte de quem compra, mas
longe de tudo. Em termos práticos, um IC {cuped_reg_reducao_ic:.0%} mais estreito
equivale a rodar o teste com cerca de {clientes_extras_equivalentes:.0%} mais clientes.
A tabela completa por covariável está em `reports/20_placar_experimento/04_cuped.csv`.

## 4. Poder

- Com {n_t:,} por braço e taxa-base de {taxa_c:.1%}, o menor efeito detectável
  (α = 5%, poder 80%) é **{mde_pp:.2f} p.p.** O efeito observado é cerca de
  {efeito_em_mdes:.0f} vezes isso: o teste tinha folga.
- Num decil (cerca de 10 mil por braço) o MDE sobe para **{mde_decil_pp:.2f} p.p.**:
  diferenças entre segmentos menores que isso não são confiáveis.

## 5. Métrica de proteção

A base não tem gasto depois da campanha (ADR 0002), então não dá para medir se a campanha
derrubou o ticket. O que dá para ver é o efeito por faixa de ticket histórico: vai de
{ticket_min_pp:+.1f} p.p. (decil {ticket_min_nivel}) a {ticket_max_pp:+.1f} p.p.
(decil {ticket_max_nivel}). Num próximo teste, o
gasto pós-campanha precisa ser coletado como métrica de proteção definida antes do início.

## 6. Efeito por segmento

{segmentos_significativos} de {segmentos_total} segmentos têm efeito diferente de zero depois
da correção de Benjamini-Hochberg (q < 5%). O mais útil é onde o efeito **muda**:

- **Gasto:** decil que menos gasta vs. decil que mais gasta: {gasto_dif_pp:+.1f} p.p.
  (IC [{gasto_ic_inf_pp:.1f}; {gasto_ic_sup_pp:.1f}], p = {gasto_p:.1e}).
- **Recência:** quartil que comprou há mais tempo vs. o mais recente: {recencia_dif_pp:+.1f} p.p.
  (IC [{recencia_ic_inf_pp:.1f}; {recencia_ic_sup_pp:.1f}], p = {recencia_p:.1e}).

Todo cliente do experimento comprou nos 23 dias anteriores ao corte, então não existe o
segmento "inativo há mais de 30 dias"; o recorte de recência usa 14 dias e quartis.

![efeito por segmento](figuras/efeito_por_segmento.png)

{tabela_segmentos}
