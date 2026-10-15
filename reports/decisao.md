# Da métrica para a decisão

Gerado por `campanha decisao`. Curvas estimadas no conjunto de teste e escaladas para a
base do experimento (200,039 clientes). Modelo de uplift: `S-learner`.

## Premissas (em rublos)

| premissa | valor | de onde vem |
|---|---:|---|
| custo por contato | 3.00 | SMS em massa, sem cupom (ajustável no simulador) |
| ticket médio | 496 | média de `ticket_medio` no perfil, antes do corte |
| margem bruta | 20% | típica de varejo alimentar |
| compras por comprador incremental | 1 | conservador: o desfecho só diz se comprou |
| **valor de um comprador incremental** | **99.2** | ticket × margem × compras |

## Resultado

- **Mandar para todos:** 6,649 compradores a mais
  (IC [4,788; 8,649]), custo de 600,117 e lucro incremental
  de 59,191.
- **Metade do resultado com uma fração do custo:** mandando por uplift, 35%
  da base já trazem metade dos compradores incrementais de mandar para todos.
- **Com 30% do orçamento:** uplift traz 3,223
  (IC [2,101; 4,250]), propensão
  1,126 e aleatório 1,995.
- **Melhor ponto com estas premissas:** mandar por uplift para 15% da base,
  lucro de 159,783 (IC [83,693; 232,389]) contra
  59,191 mandando para todos.

![orçamento contra compradores incrementais](figuras/orcamento_vs_incrementais.png)

## Tabela por orçamento

| estrategia | fracao | incrementais | inf | sup | custo | lucro |
|---|---|---|---|---|---|---|
| aleatório | 0.1 | 664.92 | 478.79 | 864.87 | 60,011.7 | 5,919.06 |
| propensão | 0.1 | 207.15 | -32.03 | 475.63 | 60,011.7 | -39,470.95 |
| uplift | 0.1 | 1,914.81 | 1,262.38 | 2,479.65 | 60,011.7 | 129,854.37 |
| aleatório | 0.2 | 1,329.83 | 957.58 | 1,729.74 | 120,023.4 | 11,838.12 |
| propensão | 0.2 | 485 | 7.23 | 961.86 | 120,023.4 | -71,932.17 |
| uplift | 0.2 | 2,740.9 | 1,863.3 | 3,641.06 | 120,023.4 | 151,755.44 |
| aleatório | 0.3 | 1,994.75 | 1,436.38 | 2,594.61 | 180,035.1 | 17,757.18 |
| propensão | 0.3 | 1,126.48 | 433.78 | 1,779.52 | 180,035.1 | -68,337 |
| uplift | 0.3 | 3,222.99 | 2,100.92 | 4,249.75 | 180,035.1 | 139,545.47 |
| aleatório | 0.5 | 3,324.58 | 2,393.96 | 4,324.35 | 300,058.5 | 29,595.3 |
| propensão | 0.5 | 2,781.26 | 1,759.35 | 3,737.66 | 300,058.5 | -24,277.76 |
| uplift | 0.5 | 4,569.6 | 3,250.69 | 6,013.71 | 300,058.5 | 153,047.45 |
| aleatório | 0.7 | 4,654.41 | 3,351.55 | 6,054.08 | 420,081.9 | 41,433.42 |
| propensão | 0.7 | 4,253.39 | 2,865.38 | 5,689.94 | 420,081.9 | 1,670.2 |
| uplift | 0.7 | 5,178.14 | 3,507.88 | 6,780.11 | 420,081.9 | 93,365.21 |
| aleatório | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |
| propensão | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |
| uplift | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |

## Sensibilidade às premissas

Melhor fração da base para mandar por uplift e lucro, variando custo por contato e margem:

| custo_por_contato | margem | melhor_fracao | lucro_melhor | lucro_mandar_para_todos |
|---|---|---|---|---|
| 1 | 0.15 | 1 | 294,441.7 | 294,441.7 |
| 1 | 0.2 | 1 | 459,268.6 | 459,268.6 |
| 1 | 0.3 | 1 | 788,922.4 | 788,922.4 |
| 3 | 0.15 | 0.15 | 97,332.52 | -105,636.3 |
| 3 | 0.2 | 0.15 | 159,782.54 | 59,190.6 |
| 3 | 0.3 | 1 | 388,844.4 | 388,844.4 |
| 6 | 0.15 | 0.1 | 22,376.15 | -705,753.3 |
| 6 | 0.2 | 0.1 | 69,842.67 | -540,926.4 |
| 6 | 0.3 | 0.15 | 194,665.03 | -211,272.6 |
| 10 | 0.15 | 0.05 | -19,372.37 | -1,505,909.3 |
| 10 | 0.2 | 0.05 | 7,510.01 | -1,341,082.4 |
| 10 | 0.3 | 0.1 | 84,760.11 | -1,011,428.6 |
