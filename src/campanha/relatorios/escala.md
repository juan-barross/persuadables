# Prova de escala: o placar na Criteo

Gerado por `campanha escala`. As mesmas consultas do placar da X5 (sorteio, balanço com
`UNPIVOT`, efeito com IC e CUPED), reescritas para a Criteo Uplift v2.1 em
`sql/30_escala_criteo/`.

## Tempo e memória

**{linhas:,} linhas, {segundos:.1f} s no total, pico de memória do processo de {pico_memoria_mb:,.0f} MB**,
lendo direto de um Parquet de {parquet_mb:.0f} MB.

{tabela_medicoes}

Máquina: {sistema}, {cpu_logicas} CPUs lógicas, {ram_total_gb:.0f} GB de RAM,
DuckDB {versao_duckdb} com {threads_duckdb} threads. O pico é do processo Python inteiro
(inclui pandas e o próprio DuckDB) e é cumulativo: cada linha mostra o maior valor até ali.

## O que o placar diz

- **Sorteio:** {sorteio[prop_tratamento]:.4%} de tratados, contra 85% esperados
  (χ² = {sorteio[qui2_vs_85pct]:.2f}). A exposição ao anúncio é {sorteio[exposicao_tratados]:.2%} nos
  tratados e {sorteio[exposicao_controle]:.2%} no controle: por isso o tratamento é `treatment`, e
  não `exposure`, que depende do usuário.
- **Balanço:** maior |SMD| entre as 12 variáveis = {max_abs_smd:.4f}.
- **Visita:** {visita[taxa_c]:.2%} no controle, efeito de
  {visita[efeito_pp]:+.3f} p.p. (IC [{visita[ic_inf_pp]:.3f};
  {visita[ic_sup_pp]:.3f}]), {visita[efeito_relativo_pct]:+.1f}% relativo.
- **Conversão:** {conversao[taxa_c]:.3%} no controle, efeito de
  {conversao[efeito_pp]:+.4f} p.p. (IC [{conversao[ic_inf_pp]:.4f};
  {conversao[ic_sup_pp]:.4f}]), {conversao[efeito_relativo_pct]:+.1f}% relativo.
- **CUPED em visita:** a melhor covariável (`{cuped[covariavel]}`) reduz a variância em
  {cuped[reducao_variancia]:.1%} e o IC em {cuped[reducao_largura_ic]:.1%}.

{tabela_efeito}
