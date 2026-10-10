# ADR 0002: desfecho principal é `target`; a métrica de proteção fica registrada como limitação

**Status:** aceita

## Contexto

`uplift_train` traz, por cliente, `treatment_flg` (recebeu a comunicação) e `target`
(comprou no período depois dela). Não há valor gasto depois da campanha: `purchases`
termina em 2019-03-18 (ADR 0001).

O plano pedia uma métrica de proteção: "a campanha não pode derrubar o ticket médio".

## Decisão

1. **Desfecho principal:** `target`, binário. O efeito é a diferença de proporções entre
   tratados e controle, reportada em pontos percentuais e em compras incrementais.
2. **Proteção:** não dá para medir ticket pós-campanha com esta base. Em vez de inventar
   um proxy, o placar registra a limitação e mede o que é possível medir sem olhar o
   futuro: o desfecho por faixa de ticket histórico, para ver se a campanha ajuda só os
   clientes de ticket baixo (o que, numa base com gasto, seria o sinal de alerta).
3. **Covariável do CUPED:** número de transações e gasto antes do corte (ADR 0001).

## Consequências

- O retorno financeiro no simulador usa premissa explícita de valor por compra
  incremental (ticket médio histórico vezes margem), com sensibilidade.
- Num experimento real, a métrica de proteção seria definida antes de rodar o teste.
  Isso entra no memorando como recomendação.
