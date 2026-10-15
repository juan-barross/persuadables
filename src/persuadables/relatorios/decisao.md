# Da métrica para a decisão

Gerado por `persuadables decisao`. Curvas estimadas no conjunto de teste e escaladas para a
base do experimento ({n_base:,} clientes). Modelo de uplift: `{modelo_uplift}`.

## Premissas (em rublos)

| premissa | valor | de onde vem |
|---|---:|---|
| custo por contato | {custo_por_contato:.2f} | SMS em massa, sem cupom (ajustável no simulador) |
| ticket médio | {ticket_base:.0f} | média de `ticket_medio` no perfil, antes do corte |
| margem bruta | {margem:.0%} | típica de varejo alimentar |
| compras por comprador incremental | {compras_por_comprador:.0f} | conservador: o desfecho só diz se comprou |
| **valor de um comprador incremental** | **{valor_por_comprador:.1f}** | ticket × margem × compras |

## Resultado

- **Mandar para todos:** {todos[incrementais]:,.0f} compradores a mais
  (IC [{todos[inf]:,.0f}; {todos[sup]:,.0f}]), custo de {todos[custo]:,.0f} e lucro incremental
  de {todos[lucro]:,.0f}.
- **Metade do resultado com uma fração do custo:** mandando por uplift, {fracao_metade:.0%}
  da base já trazem metade dos compradores incrementais de mandar para todos.
- **Com 30% do orçamento:** uplift traz {com_30_uplift[incrementais]:,.0f}
  (IC [{com_30_uplift[inf]:,.0f}; {com_30_uplift[sup]:,.0f}]), propensão
  {com_30_propensao[incrementais]:,.0f} e aleatório {com_30_aleatorio[incrementais]:,.0f}.
- **Melhor ponto com estas premissas:** mandar por uplift para {melhor[fracao]:.0%} da base,
  lucro de {melhor[lucro]:,.0f} (IC [{melhor[lucro_inf]:,.0f}; {melhor[lucro_sup]:,.0f}]) contra
  {todos[lucro]:,.0f} mandando para todos.

![orçamento contra compradores incrementais](figuras/orcamento_vs_incrementais.png)

## Tabela por orçamento

{tabela_orcamento}

## Sensibilidade às premissas

Melhor fração da base para mandar por uplift e lucro, variando custo por contato e margem:

{tabela_sensibilidade}
