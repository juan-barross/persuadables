# Prova de escala: o placar na Criteo

Gerado por `persuadables escala`. As mesmas consultas do placar da X5 (sorteio, balanço com
`UNPIVOT`, efeito com IC e CUPED), reescritas para a Criteo Uplift v2.1 em
`sql/30_escala_criteo/`.

## Tempo e memória

**13,979,592 linhas, 5.2 s no total, pico de memória do processo de 171 MB**,
lendo direto de um Parquet de 177 MB.

| consulta | segundos | linhas_por_segundo_mi | pico_memoria_processo_mb |
|---|---|---|---|
| 01_sorteio | 0.16 | 85.27 | 107.73 |
| 02_balanco | 2.69 | 5.2 | 169.44 |
| 03_efeito | 0.5 | 28.06 | 169.44 |
| 04_cuped | 1.82 | 7.66 | 170.98 |

Máquina: Windows 11, 8 CPUs lógicas, 4 GB de RAM,
DuckDB 1.5.6 com 8 threads. O pico é do processo Python inteiro
(inclui pandas e o próprio DuckDB) e é cumulativo: cada linha mostra o maior valor até ali.

## O que o placar diz

- **Sorteio:** 85.0000% de tratados, contra 85% esperados
  (χ² = 0.00). A exposição ao anúncio é 3.60% nos
  tratados e 0.00% no controle: por isso o tratamento é `treatment`, e
  não `exposure`, que depende do usuário.
- **Balanço:** maior |SMD| entre as 12 variáveis = 0.0488.
- **Visita:** 3.82% no controle, efeito de
  +1.034 p.p. (IC [1.006;
  1.063]), +27.1% relativo.
- **Conversão:** 0.194% no controle, efeito de
  +0.1152 p.p. (IC [0.1085;
  0.1219]), +59.4% relativo.
- **CUPED em visita:** a melhor covariável (`f9`) reduz a variância em
  22.3% e o IC em 11.9%.

| desfecho | taxa_t | taxa_c | efeito_pp | ic_inf_pp | ic_sup_pp | efeito_relativo_pct | z |
|---|---|---|---|---|---|---|---|
| visit | 0.0485 | 0.0382 | 1.0342 | 1.0056 | 1.0629 | 27.0737 | 70.6852 |
| conversion | 0.0031 | 0.0019 | 0.1152 | 0.1085 | 0.1219 | 59.4488 | 33.5123 |
