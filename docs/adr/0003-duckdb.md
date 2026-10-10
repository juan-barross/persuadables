# ADR 0003: DuckDB sobre Parquet como motor de SQL

**Status:** aceita

## Contexto

`purchases` tem 45,8 milhões de linhas (4 GB de CSV). No pandas, só carregar já passa
da memória de um notebook comum. O projeto precisa de SQL de verdade (janelas,
`FILTER`, `QUANTILE_CONT`) e de rodar igual na CI, sem servidor.

## Decisão

- CSV.gz é convertido uma vez para Parquet com zstd pelo próprio DuckDB
  (`src/campanha/ingest.py`). `purchases` cai de 638 MB (gz) para 466 MB, com tipos.
- As consultas leem o Parquet por views (`run_sql.conectar`), sem carregar tudo em memória.
- Os `.sql` ficam em `sql/` e rodam em ordem pelo `run_sql.py`, de modo que qualquer
  pessoa pode ler e reexecutar a análise sem abrir um notebook.

## Alternativas

- **Postgres:** exige servidor e carga lenta; não roda na CI sem Docker.
- **Polars:** rápido, mas o objetivo aqui é mostrar SQL analítico.
- **Spark:** exagero para 45 milhões de linhas numa máquina só.

## Consequências

A auditoria inteira roda em cerca de 3,5 minutos num notebook com Windows. O tempo e a
memória da Criteo (14 milhões de linhas) ficam medidos em `reports/escala_criteo.md`.
