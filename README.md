# Persuadables

Peguei o teste de campanha da X5 RetailHero, uma rede de varejo russa: 200 mil clientes, metade
sorteada para receber a mensagem, e 45,8 milhões de itens comprados antes do envio. A pergunta
é para quem vale mandar. Persuadables é como a literatura de uplift chama quem só compra se
receber a campanha.

![Orçamento contra compradores incrementais](reports/figuras/orcamento_vs_incrementais.png)

## Resultado

A taxa de compra foi de 60,3% para 63,7% (+3,3 p.p., IC 95% de 2,9 a 3,7). Quase todo mundo
que comprou depois da mensagem teria comprado sem ela.

Quem mais reage é quem gastava pouco e estava há mais tempo sem comprar: +7,2 p.p. no decil de
menor gasto, cerca de 1 p.p. no de maior. O modelo de propensão faz o contrário e coloca no topo
quem compra mais de 95% das vezes sem campanha. Nos 30% que ele escolhe o efeito cai para
1,9 p.p., abaixo de mandar ao acaso. O S-learner acha 5,4 p.p. nos seus 30%, e ali estão 48% dos
compradores incrementais.

Com ₽ 3 por contato e margem de 20%, mandar por uplift para 15% da base rende ₽ 160 mil de lucro
incremental (IC de 84 a 232 mil). Mandar para todo mundo rende ₽ 59 mil com quase sete vezes
mais contatos. Escrevi a recomendação para o CRM no [memorando](docs/memorando.md), e o
simulador em Streamlit refaz a conta se você mudar custo e margem.

Também tem um agente que responde perguntas do gerente lendo os relatórios e chamando a conta de
lucro. Rodei num modelo gratuito (Nemotron 3 Ultra, pela OpenRouter) e ele acertou 9 de 10
perguntas com resposta conhecida. Errou a que exige comparar 20 orçamentos
([`reports/agente.md`](reports/agente.md)).

## Rodar

Precisa de Python 3.12 e [uv](https://docs.astral.sh/uv/). Dá para rodar sem baixar nada, numa
amostra sintética que imita as anomalias da base real:

```bash
uv sync --all-extras
```

```bash
uv run persuadables --amostra tudo
```

```bash
uv run streamlit run app/streamlit_app.py
```

Com os dados reais (uns 650 MB da X5 e 310 MB da Criteo) é `uv run persuadables tudo`. Cada etapa
também roda sozinha: `baixar`, `auditar`, `perfil`, `placar`, `uplift`, `decisao` e `escala`.

O agente precisa de uma chave da OpenRouter num `.env` (copie o `.env.example`):

```bash
uv run --env-file .env persuadables perguntar "Qual o lucro mandando por uplift para 20% da base com contato a 4 rublos?"
```

`avaliar-agente` roda as dez perguntas de teste. O padrão é o Opus 5.5; para trocar, use
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

As escolhas de projeto ficaram anotadas em [`docs/adr`](docs/adr).

| Modelo (teste, 40 mil clientes) | AUUC | Qini | Efeito nos 30% de maior score | Incrementais nos 30% |
|---|---:|---:|---:|---:|
| S-learner | 0,015 | 0,009 | +5,4 p.p. | 48% |
| X-learner | 0,014 | 0,009 | +5,3 p.p. | 47% |
| T-learner | 0,010 | 0,006 | +4,9 p.p. | 44% |
| Class transformation | 0,007 | 0,004 | +4,3 p.p. | 39% |
| Propensão | -0,007 | -0,005 | +1,9 p.p. | 17% |

![Curva Qini](reports/figuras/curva_qini.png)

![Efeito por segmento](reports/figuras/efeito_por_segmento.png)

## O que deu errado no caminho

A base tem armadilhas. 44.953 clientes fizeram o primeiro resgate de pontos depois da data de
corte, e se essa data entrasse no perfil o modelo estaria olhando o futuro; ela vira nulo.
`purchase_sum` vem repetido em cada item da compra, então o perfil agrega por transação antes de
somar. E 28 `transaction_id` aparecem em clientes diferentes: agrupando só pelo id, a auditoria
dava um número diferente a cada execução, até eu mudar o grão para cliente e transação.

Eu queria separar os "inativos há mais de 30 dias", mas todo cliente do teste comprou nos 23 dias
antes do corte. Fiquei com 14 dias e quartis de recência.

O CUPED na Criteo estourou os 4 GB de RAM do notebook com `UNPIVOT` e `JOIN`. Reescrevi com somas
por grupo (n, Σy, Σy², Σx, Σx², Σxy); agora roda em segundos e bate com a versão em Python. No
mesmo SQL, o `sqlfluff fix` transformou um `COUNT(DISTINCT (a, b))` em algo que o DuckDB não
aceita.

O mais chato de achar: somas de `DOUBLE` em paralelo mexiam no perfil na casa de 1e-10 a cada
execução. Era o bastante para o LightGBM mudar e o melhor orçamento pular de 30% para 15%. Com
`DECIMAL` e horas inteiras o resultado parou de oscilar, e há um teste para isso.

Por último, o saldo da OpenRouter acabou no meio da avaliação com o Opus 5.5, e o modelo gratuito
só aceita 50 pedidos por dia. O cliente tenta de novo até 8 vezes e o relatório pode ser refeito
a partir do CSV salvo.

## Testes

`uv run pytest` roda 63 testes. O que mais me importa é o de vazamento: apagar ou alterar tudo
depois da data de corte não pode mudar o perfil, numa amostra com compras plantadas no futuro e
uma exatamente no instante do corte. A estatística é conferida contra statsmodels e simulação, o
SQL da Criteo contra Python, e o pipeline inteiro roda na amostra sem perder linhas e achando o
efeito no segmento onde foi plantado. O agente é testado com um cliente falso, sem gastar chave.

A CI roda ruff, sqlfluff, os testes e o pipeline na amostra. Num notebook com 4 GB de RAM, a
auditoria das 45,8 milhões de linhas leva uns 80 s, o perfil 20 s e o placar na Criteo
(14 milhões de linhas) de 5 a 14 s.

## Limitações

É uma campanha só, de março de 2019. Antes de usar isso de verdade eu repetiria o teste com um
grupo de controle dentro do público escolhido. A base diz se o cliente comprou, mas não quanto
gastou ([ADR 0002](docs/adr/0002-desfecho-e-protecao.md)). Custo por contato e margem são
premissas minhas; a sensibilidade está em [`decisao.md`](reports/decisao.md).

## Dados

- X5 RetailHero, via [scikit-uplift](https://www.uplift-modeling.com/en/latest/api/datasets/fetch_x5.html)
  ([competição original](https://ods.ai/competitions/x5-retailhero-uplift-modeling/data)). Não tem
  licença publicada, então os dados não estão no repositório; `persuadables baixar` busca na fonte.
- Criteo Uplift v2.1 ([página oficial](https://ailab.criteo.com/?p=859)), CC BY-NC-SA 4.0. Baixei
  de um [espelho](https://github.com/jszymon/uplift_sklearn_data/releases) porque o link original
  dava 404. Diemert et al., *A Large Scale Benchmark for Uplift Modeling*, AdKDD 2018.
- Código sob licença MIT.
