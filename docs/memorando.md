# Memorando: para quem mandar a próxima campanha

**Para:** gerência de CRM
**Assunto:** resultado do teste da comunicação de março/2019 e recomendação de público
**Base:** experimento randomizado com 200.039 clientes da X5 (metade recebeu a comunicação)

## Recomendação

Mandar a próxima campanha só para **os 30% de clientes com maior uplift previsto**, e não para a
base inteira. Com as premissas abaixo, isso rende **₽ 156 mil de lucro incremental** contra
₽ 59 mil mandando para todos, com 70% menos contatos.

## O que o teste mostrou

1. **A campanha funciona, mas pouco em termos absolutos.** A taxa de compra passou de 60,3% no
   controle para 63,7% nos que receberam: **+3,3 p.p.** (IC 95% de 2,9 a 3,7). São cerca de
   3.300 compradores a mais a cada 100 mil contatos. Ou seja, 95 de cada 100 compras dos que
   receberam a mensagem teriam acontecido sem ela.
2. **O efeito não é igual para todos.** Nos 10% que menos gastavam antes, a campanha somou
   7,2 p.p.; nos 10% que mais gastavam, cerca de 1 p.p. Clientes que compram com menos
   frequência, estão há mais dias sem comprar e são mais velhos (mediana de 58 anos contra 39)
   são os que mudam de comportamento.
3. **Escolher pelos "melhores clientes" é o erro mais caro.** Um modelo que ordena por chance
   de compra (o critério usual) põe no topo quem compraria 95% das vezes de qualquer jeito. Nos
   30% que ele escolhe o efeito da campanha é de 1,6 p.p., abaixo do envio aleatório. O modelo
   de uplift, nos 30% que escolhe, encontra 5,6 p.p. e já concentra metade de todos os
   compradores incrementais.

## Quanto vale

| | mandar para todos | uplift, 30% da base |
|---|---:|---:|
| contatos | 200 mil | 60 mil |
| compradores a mais | 6.650 (IC 4.800 a 8.650) | 3.390 (IC 2.260 a 4.530) |
| custo dos contatos | ₽ 600 mil | ₽ 180 mil |
| lucro incremental | ₽ 59 mil | **₽ 156 mil** (IC 44 mil a 269 mil) |

Premissas: ₽ 3 por contato, ticket de ₽ 496 (média histórica), margem de 20% e uma compra por
comprador incremental. Se o contato custar ₽ 6, mandar para todos dá **prejuízo de ₽ 541 mil**,
enquanto os 10% de maior uplift ainda dão ₽ 82 mil. Com contato a ₽ 1, mandar para quase todos
passa a compensar. O simulador permite testar outras premissas.

## Riscos e o que fazer a respeito

- **Uma campanha, uma época.** O modelo aprendeu com uma única comunicação em março/2019. Antes
  de escalar, repetir com um grupo de controle aleatório de 10% dentro do público escolhido,
  para medir o efeito real da seleção.
- **Faltou medir gasto.** O teste só registrou se o cliente comprou, não quanto. A próxima
  rodada precisa de uma métrica de proteção definida antes (ticket e gasto nos 30 dias
  seguintes), para ter certeza de que a campanha não troca compras grandes por pequenas.
- **Premissas de dinheiro.** Margem e custo são estimativas. A recomendação de mandar para uma
  fatia pequena vale com contato a ₽ 3 e margem de até 20%, e com contato a partir de ₽ 6 em
  qualquer margem testada (15% a 30%). Com contato a ₽ 1, ou a ₽ 3 com margem de 30%, o melhor
  passa a ser mandar para quase todos.
- **Público do teste.** Todos os clientes do experimento tinham comprado nos 23 dias anteriores.
  Para clientes inativos há mais tempo, este teste não diz nada.
