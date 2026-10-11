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
- **Metade do resultado com uma fração do custo:** mandando por uplift, 30%
  da base já trazem metade dos compradores incrementais de mandar para todos.
- **Com 30% do orçamento:** uplift traz 3,390
  (IC [2,261; 4,533]), propensão
  972 e aleatório 1,995.
- **Melhor ponto com estas premissas:** mandar por uplift para 30% da base,
  lucro de 156,147 (IC [44,200; 269,463]) contra
  59,191 mandando para todos.

![orçamento contra compradores incrementais](figuras/orcamento_vs_incrementais.png)

## Tabela por orçamento

| estrategia | fracao | incrementais | inf | sup | custo | lucro |
|---|---|---|---|---|---|---|
| aleatório | 0.1 | 664.92 | 478.79 | 864.87 | 60,011.7 | 5,919.06 |
| propensão | 0.1 | 235.68 | 12.31 | 539.06 | 60,011.7 | -36,642.08 |
| uplift | 0.1 | 2,040.02 | 1,404.57 | 2,698.41 | 60,011.7 | 142,270.16 |
| aleatório | 0.2 | 1,329.83 | 957.58 | 1,729.74 | 120,023.4 | 11,838.12 |
| propensão | 0.2 | 314.43 | -145.75 | 782.19 | 120,023.4 | -88,845.94 |
| uplift | 0.2 | 2,721.8 | 1,786.52 | 3,573.17 | 120,023.4 | 149,861.5 |
| aleatório | 0.3 | 1,994.75 | 1,436.38 | 2,594.61 | 180,035.1 | 17,757.18 |
| propensão | 0.3 | 972.17 | 339.56 | 1,656.81 | 180,035.1 | -83,637.77 |
| uplift | 0.3 | 3,390.41 | 2,261.43 | 4,533.21 | 180,035.1 | 156,146.76 |
| aleatório | 0.5 | 3,324.58 | 2,393.96 | 4,324.35 | 300,058.5 | 29,595.3 |
| propensão | 0.5 | 2,714.19 | 1,704.9 | 3,757.82 | 300,058.5 | -30,928.04 |
| uplift | 0.5 | 3,996.85 | 2,689.76 | 5,341.01 | 300,058.5 | 96,255.38 |
| aleatório | 0.7 | 4,654.41 | 3,351.55 | 6,054.08 | 420,081.9 | 41,433.42 |
| propensão | 0.7 | 4,219.24 | 2,819.6 | 5,564.69 | 420,081.9 | -1,716.36 |
| uplift | 0.7 | 5,145.82 | 3,528.98 | 6,910.67 | 420,081.9 | 90,160.06 |
| aleatório | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |
| propensão | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |
| uplift | 1 | 6,649.15 | 4,787.92 | 8,648.69 | 600,117 | 59,190.6 |

## Sensibilidade às premissas

Melhor fração da base para mandar por uplift e lucro, variando custo por contato e margem:

| custo_por_contato | margem | melhor_fracao | lucro_melhor | lucro_mandar_para_todos |
|---|---|---|---|---|
| 1 | 0.15 | 0.95 | 311,071.09 | 294,441.7 |
| 1 | 0.2 | 0.95 | 478,107.13 | 459,268.6 |
| 1 | 0.3 | 0.95 | 812,179.22 | 788,922.4 |
| 3 | 0.15 | 0.15 | 93,044.87 | -105,636.3 |
| 3 | 0.2 | 0.3 | 156,146.76 | 59,190.6 |
| 3 | 0.3 | 0.95 | 432,105.12 | 388,844.4 |
| 6 | 0.15 | 0.1 | 31,687.99 | -705,753.3 |
| 6 | 0.2 | 0.1 | 82,258.46 | -540,926.4 |
| 6 | 0.3 | 0.15 | 186,089.73 | -211,272.6 |
| 10 | 0.15 | 0.05 | -16,651.84 | -1,505,909.3 |
| 10 | 0.2 | 0.05 | 11,137.38 | -1,341,082.4 |
| 10 | 0.3 | 0.1 | 103,383.79 | -1,011,428.6 |
