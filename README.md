# Persuadables

Um varejista mandou uma comunicação para metade de 200 mil clientes, escolhidos por sorteio.
Aqui eu leio esse experimento, descubro em quem a campanha muda o comportamento e transformo
isso numa decisão de orçamento. Os dados são reais (X5 RetailHero, 45,8 milhões de itens
comprados), o perfil dos clientes é montado em SQL e o resultado sai em rublos.

Em uplift, *persuadables* são os clientes que só compram se receberem a campanha. São eles
que este projeto procura.

![Orçamento contra compradores incrementais](reports/figuras/orcamento_vs_incrementais.png)

## Resultado

| Pergunta | Resposta |
|---|---|
| A campanha funciona? | Sim, pouco. A taxa de compra vai de 60,3% para 63,7%: +3,3 p.p. (IC 95% de 2,9 a 3,7). |
| Para quem? | Para quem gasta pouco, compra pouco e está há mais dias sem comprar. No decil que menos gasta o efeito é +7,2 p.p.; no que mais gasta, perto de 1 p.p. |
| Mandar para os melhores clientes funciona? | Não. O modelo de propensão põe no topo quem compraria mais de 95% das vezes sem campanha. Nos 30% que ele escolhe o efeito é de 1,9 p.p., abaixo do envio aleatório. |
| E um modelo de uplift? | Nos 30% de maior score o efeito é de 5,4 p.p., e esses clientes concentram 48% dos compradores incrementais. |
| Quanto vale? | Com ₽ 3 por contato e margem de 20%, mandar por uplift para 15% da base dá ₽ 160 mil de lucro incremental (IC de 84 a 232 mil). Mandar para todos dá ₽ 59 mil, com quase sete vezes mais contatos. |

A recomendação para o gerente de CRM, com riscos, está no [memorando de uma página](docs/memorando.md).
O simulador em Streamlit deixa mudar custo, ticket, margem e orçamento.

## Rodar em um minuto

Precisa de Python 3.12 e [uv](https://docs.astral.sh/uv/). Sem baixar nada, com uma amostra
sintética que tem as mesmas anomalias da base real:

```bash
uv sync --all-extras
```

```bash
uv run persuadables --amostra tudo
```

```bash
uv run streamlit run app/streamlit_app.py
```

Com os dados reais (cerca de 650 MB da X5 e 310 MB da Criteo), `uv run persuadables tudo`.
Cada etapa também roda sozinha: `baixar`, `auditar`, `perfil`, `placar`, `uplift`,
`decisao --custo 3 --margem 0.2` e `escala`.

## Como foi feito

| Etapa | Código | Saída |
|---|---|---|
| Auditoria | [`sql/00_auditoria`](sql/00_auditoria) | [`reports/auditoria.md`](reports/auditoria.md): chaves, datas, valores e distribuições |
| Perfil do cliente | [`sql/10_perfil_cliente`](sql/10_perfil_cliente) | 36 variáveis por cliente, só com dados anteriores à campanha: recência com `LAG`, gasto em janelas com `FILTER`, tendência em meses móveis, decis com `NTILE` |
| Placar do experimento | [`sql/20_placar_experimento`](sql/20_placar_experimento), [`placar.py`](src/persuadables/placar.py) | [`reports/placar.md`](reports/placar.md): sorteio, balanço, efeito com IC, CUPED, poder e segmentos com Benjamini-Hochberg |
| Uplift | [`uplift.py`](src/persuadables/uplift.py) | [`reports/uplift.md`](reports/uplift.md): propensão contra S-, T-, X-learner e class transformation |
| Decisão | [`decisao.py`](src/persuadables/decisao.py) | [`reports/decisao.md`](reports/decisao.md): compradores e lucro por orçamento, com IC e sensibilidade |
| Escala | [`sql/30_escala_criteo`](sql/30_escala_criteo) | [`reports/escala_criteo.md`](reports/escala_criteo.md): o mesmo placar em 14 milhões de linhas |

As decisões de projeto estão em [`docs/adr`](docs/adr).

### Modelos (conjunto de teste, 40 mil clientes)

| Modelo | AUUC | Qini | Efeito nos 30% de maior score | Incrementais nos 30% |
|---|---:|---:|---:|---:|
| S-learner (escolhido na validação) | 0,015 | 0,009 | +5,4 p.p. | 48% |
| X-learner | 0,014 | 0,009 | +5,3 p.p. | 47% |
| T-learner | 0,010 | 0,006 | +4,9 p.p. | 44% |
| Class transformation | 0,007 | 0,004 | +4,3 p.p. | 39% |
| Propensão | -0,007 | -0,005 | +1,9 p.p. | 17% |

![Curva Qini](reports/figuras/curva_qini.png)

Os 20% com maior uplift previsto, comparados aos 20% com menor, têm mediana de 9 compras
contra 32, gastaram 2,8 mil rublos contra 13,1 mil, estão há 7,4 dias sem comprar contra 2,5
e têm 58 anos contra 40. Sem campanha, 46% deles comprariam; no outro grupo, 73%.

![Efeito por segmento](reports/figuras/efeito_por_segmento.png)

## O que deu errado no caminho

- Não há compra depois da data de corte, mas 44.953 clientes têm o primeiro resgate de pontos
  depois dela. Usar essa data seria olhar o futuro, então ela vira nulo no perfil.
- `purchase_sum` é o valor da compra repetido em cada item. Somar direto multiplica o gasto
  pelo número de itens; o perfil agrega primeiro por transação.
- 28 `transaction_id` aparecem com dois clientes, duas lojas e dois horários. Agrupando só
  pelo id, a contagem por dia da semana mudava de uma execução para outra. O grão passou a
  ser cliente mais transação.
- O plano previa olhar inativos há mais de 30 dias, mas todo cliente do experimento comprou
  nos 23 dias anteriores ao corte. O recorte virou 14 dias e quartis de recência.
- Na Criteo, o CUPED com `UNPIVOT` e `JOIN` estourou os 4 GB do notebook. Reescrito com
  estatísticas suficientes (n, Σy, Σy², Σx, Σx², Σxy por grupo), roda em 2,6 s e bate com a
  versão em Python até a sexta casa decimal.
- O `sqlfluff fix` trocou `COUNT(DISTINCT (a, b))` por `COUNT(DISTINCT a, b)`, que o DuckDB
  não aceita. Só apareceu porque a auditoria roda de novo depois de cada mudança.
- O perfil mudava em até 1e-10 entre execuções, porque o DuckDB soma `DOUBLE` em paralelo em
  ordem variável. Parece nada, mas mudava os splits do LightGBM e levava o melhor orçamento de
  30% para 15% da base. Com valores em `DECIMAL` e intervalos em horas inteiras, duas execuções
  dão relatórios idênticos, e um teste garante isso.

## Testes

```bash
uv run pytest
```

- O teste de vazamento foi escrito antes do perfil: apagar ou alterar tudo o que aconteceu a
  partir da data de corte não pode mudar uma casa decimal do perfil. Como a base real não tem
  compras futuras, ele roda numa amostra sintética com compras plantadas depois do corte e uma
  no instante exato do corte. Trocando `<` por `<=` no SQL, ele falha.
- A estatística é conferida contra statsmodels e contra simulação.
- O SQL da Criteo é conferido contra a mesma conta em Python.
- O pipeline inteiro roda na amostra: nenhuma linha some entre as etapas e o efeito plantado
  aparece no segmento certo.

- Cada módulo tem testes de unidade com dados pequenos e conhecidos: formatação dos relatórios,
  conversão para Parquet, conta do lucro, divisão estratificada, escolha do modelo e a CLI.

São 53 testes, que rodam em cerca de um minuto. A CI roda ruff, sqlfluff, os testes e o
pipeline completo na amostra.

## Desempenho

Num notebook Windows com 8 CPUs lógicas e 4 GB de RAM, lendo direto do Parquet:

| Etapa | Linhas | Tempo |
|---|---:|---:|
| Placar completo na Criteo | 13.979.592 | 5 a 14 s, conforme a carga da máquina (pico de 110 a 170 MB) |
| Auditoria da X5 | 45.786.568 itens | cerca de 80 s |
| Perfil do cliente | 45.786.568 itens | cerca de 20 s |
| Amostra sintética | 120 mil itens | 0,6 s |
| Bootstrap da decisão (500 reamostras, 3 estratégias) | 40 mil clientes | 1,9 s |

Na Criteo a visita sobe 1,03 p.p. (+27%) e a conversão 0,115 p.p. (+59%). O tratamento é
`treatment`, que foi sorteado, e não `exposure`, que depende do usuário.

## Limitações

- Uma campanha só, de março de 2019. Antes de usar em produção, o certo é repetir o teste com
  um grupo de controle aleatório dentro do público escolhido.
- A base diz se o cliente comprou depois, não quanto. Não dá para saber se a campanha trocou
  compras grandes por pequenas ([ADR 0002](docs/adr/0002-desfecho-e-protecao.md)).
- Custo por contato e margem são premissas. A sensibilidade está em
  [`reports/decisao.md`](reports/decisao.md) e no simulador.
- Todos os clientes do experimento tinham comprado nas três semanas anteriores.

## Dados e licença

- X5 RetailHero, via [scikit-uplift](https://www.uplift-modeling.com/en/latest/api/datasets/fetch_x5.html)
  (competição original na [ods.ai](https://ods.ai/competitions/x5-retailhero-uplift-modeling/data)).
  Não encontrei licença publicada, então os dados não estão no repositório; `persuadables baixar`
  busca na fonte.
- Criteo Uplift v2.1 ([Criteo AI Lab](https://ailab.criteo.com/?p=859)), CC BY-NC-SA 4.0.
  Diemert, Betlei, Renaudin e Amini, *A Large Scale Benchmark for Uplift Modeling*, AdKDD 2018.
  O link usado pelo scikit-uplift dava 404 em outubro de 2026; o download usa o
  [espelho da libuplift](https://github.com/jszymon/uplift_sklearn_data/releases) e confere as
  13.979.592 linhas.
- Código sob licença MIT.

DuckDB, Python 3.12, uv, pandas, statsmodels, scikit-uplift, LightGBM, Streamlit, pytest, ruff e sqlfluff.
