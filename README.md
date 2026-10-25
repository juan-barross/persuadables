# Persuadables

Análise de um teste de campanha de um varejista russo (X5 RetailHero): 200 mil clientes,
metade sorteada para receber a comunicação, e 45,8 milhões de itens comprados antes dela.
Monto o perfil dos clientes em SQL, leio o experimento, treino modelos de uplift e traduzo o
resultado em quanto mandar e para quem.

O nome vem do termo de uplift para quem só compra se receber a campanha.

![Orçamento contra compradores incrementais](reports/figuras/orcamento_vs_incrementais.png)

## Resultado

A campanha subiu a taxa de compra de 60,3% para 63,7%, um efeito de 3,3 p.p. (IC 95% de 2,9
a 3,7). Quase todo mundo que comprou depois da mensagem compraria de qualquer jeito.

O efeito se concentra em quem gastava pouco e estava há mais dias sem comprar: +7,2 p.p. no
decil de menor gasto e cerca de 1 p.p. no de maior. Por isso escolher os "melhores clientes"
dá errado. O modelo de propensão põe no topo quem compra mais de 95% das vezes sem campanha,
e nos 30% que ele escolhe o efeito é de 1,9 p.p., menos que mandar ao acaso. O S-learner acha
5,4 p.p. nos seus 30% e reúne ali 48% dos compradores incrementais.

Com ₽ 3 por contato e margem de 20%, mandar por uplift para 15% da base dá ₽ 160 mil de lucro
incremental (IC de 84 a 232 mil). Mandar para todos dá ₽ 59 mil, com quase sete vezes mais
contatos. A recomendação para o CRM está no [memorando](docs/memorando.md), e o simulador em
Streamlit refaz a conta com outras premissas.

Há também um agente que responde perguntas do gerente usando os relatórios e a conta de lucro.
Num modelo gratuito (Nemotron 3 Ultra, pela OpenRouter) ele acertou 9 de 10 perguntas com
resposta conhecida; errou a que pede comparar 20 orçamentos ([`reports/agente.md`](reports/agente.md)).

## Rodar

Precisa de Python 3.12 e [uv](https://docs.astral.sh/uv/). Sem baixar nada, numa amostra
sintética com as mesmas anomalias da base real:

```bash
uv sync --all-extras
```

```bash
uv run persuadables --amostra tudo
```

```bash
uv run streamlit run app/streamlit_app.py
```

Com os dados reais (cerca de 650 MB da X5 e 310 MB da Criteo), `uv run persuadables tudo`. As
etapas também rodam sozinhas: `baixar`, `auditar`, `perfil`, `placar`, `uplift`, `decisao` e
`escala`.

Para o agente, copie `.env.example` para `.env` com uma chave da OpenRouter:

```bash
uv run --env-file .env persuadables perguntar "Qual o lucro mandando por uplift para 20% da base com contato a 4 rublos?"
```

`avaliar-agente` roda as dez perguntas de teste. O modelo padrão é o Opus 5.5 e muda com
`PERSUADABLES_MODELO`.

## Estrutura

| Etapa | Código | Saída |
|---|---|---|
| Auditoria | [`sql/00_auditoria`](sql/00_auditoria) | [`auditoria.md`](reports/auditoria.md) |
| Perfil do cliente | [`sql/10_perfil_cliente`](sql/10_perfil_cliente) | 36 variáveis por cliente, só com dados anteriores à campanha |
| Placar do experimento | [`sql/20_placar_experimento`](sql/20_placar_experimento), [`placar.py`](src/persuadables/placar.py) | [`placar.md`](reports/placar.md): sorteio, balanço, IC, CUPED, poder, segmentos com BH |
| Uplift | [`uplift.py`](src/persuadables/uplift.py) | [`uplift.md`](reports/uplift.md): propensão contra S-, T-, X-learner e class transformation |
| Decisão | [`decisao.py`](src/persuadables/decisao.py) | [`decisao.md`](reports/decisao.md): lucro por orçamento, com IC e sensibilidade |
| Escala | [`sql/30_escala_criteo`](sql/30_escala_criteo) | [`escala_criteo.md`](reports/escala_criteo.md): o mesmo placar em 14 milhões de linhas |
| Agente | [`agente.py`](src/persuadables/agente.py) | [`agente.md`](reports/agente.md) |

As decisões de projeto estão em [`docs/adr`](docs/adr).

| Modelo (teste, 40 mil clientes) | AUUC | Qini | Efeito nos 30% de maior score | Incrementais nos 30% |
|---|---:|---:|---:|---:|
| S-learner | 0,015 | 0,009 | +5,4 p.p. | 48% |
| X-learner | 0,014 | 0,009 | +5,3 p.p. | 47% |
| T-learner | 0,010 | 0,006 | +4,9 p.p. | 44% |
| Class transformation | 0,007 | 0,004 | +4,3 p.p. | 39% |
| Propensão | -0,007 | -0,005 | +1,9 p.p. | 17% |

![Curva Qini](reports/figuras/curva_qini.png)

![Efeito por segmento](reports/figuras/efeito_por_segmento.png)

## Problemas que apareceram

- 44.953 clientes têm o primeiro resgate de pontos depois da data de corte. Essa data vira nulo
  no perfil, senão o modelo olharia o futuro.
- `purchase_sum` se repete em cada item da compra. O perfil agrega por transação antes de somar.
- 28 `transaction_id` repetem em clientes diferentes. Agrupando só pelo id, a auditoria mudava
  de uma execução para outra; o grão passou a ser cliente e transação.
- Todos os clientes do teste compraram nos 23 dias antes do corte, então não havia "inativos há
  mais de 30 dias". Usei 14 dias e quartis de recência.
- O CUPED na Criteo estourou os 4 GB de RAM com `UNPIVOT` e `JOIN`. Reescrito com somas por
  grupo (n, Σy, Σy², Σx, Σx², Σxy), roda em segundos e bate com a versão em Python.
- O `sqlfluff fix` reescreveu um `COUNT(DISTINCT (a, b))` de um jeito que o DuckDB não aceita.
- Somas de `DOUBLE` em paralelo mudavam o perfil em 1e-10 a cada execução, o suficiente para o
  LightGBM mudar e o melhor orçamento pular de 30% para 15%. Com `DECIMAL` e horas inteiras, o
  resultado ficou estável, e um teste confere isso.
- O saldo da OpenRouter acabou no meio da avaliação com Opus 5.5 e o modelo gratuito tem limite
  de 50 pedidos por dia. O cliente tenta de novo até 8 vezes e o relatório pode ser refeito a
  partir do CSV salvo.

## Testes

`uv run pytest` roda 63 testes. Os principais:

- Vazamento: apagar ou alterar tudo depois da data de corte não pode mudar o perfil. Roda numa
  amostra com compras plantadas no futuro e uma no instante exato do corte.
- Estatística conferida contra statsmodels e simulação, e o SQL da Criteo contra Python.
- O pipeline inteiro na amostra, sem perder linhas, com o efeito plantado no segmento certo.
- O agente com um cliente simulado, sem gastar chave.

A CI roda ruff, sqlfluff, os testes e o pipeline na amostra. Num notebook com 4 GB de RAM, a
auditoria das 45,8 milhões de linhas leva cerca de 80 s, o perfil 20 s e o placar na Criteo
(14 milhões de linhas) de 5 a 14 s.

## Limitações

- Uma campanha só, de março de 2019. Antes de usar de verdade, repetiria o teste com um grupo de
  controle dentro do público escolhido.
- A base diz se o cliente comprou, não quanto gastou ([ADR 0002](docs/adr/0002-desfecho-e-protecao.md)).
- Custo por contato e margem são premissas; a sensibilidade está em [`decisao.md`](reports/decisao.md).

## Dados

- X5 RetailHero, via [scikit-uplift](https://www.uplift-modeling.com/en/latest/api/datasets/fetch_x5.html)
  ([competição original](https://ods.ai/competitions/x5-retailhero-uplift-modeling/data)). Sem
  licença publicada, então os dados não estão aqui; `persuadables baixar` busca na fonte.
- Criteo Uplift v2.1 ([página oficial](https://ailab.criteo.com/?p=859)), CC BY-NC-SA 4.0,
  baixada de um [espelho](https://github.com/jszymon/uplift_sklearn_data/releases) porque o link
  original dava 404. Diemert et al., *A Large Scale Benchmark for Uplift Modeling*, AdKDD 2018.
- Código sob licença MIT.
