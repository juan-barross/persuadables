# Memorando: para quem mandar a próxima campanha

Para: gerência de CRM
Assunto: resultado do teste da comunicação de março de 2019 e público recomendado
Base: experimento com 200.039 clientes da X5, metade sorteada para receber a comunicação

## Recomendação

Mandar a próxima campanha só para os 15% de clientes com maior uplift previsto. Com as
premissas abaixo, isso rende ₽ 160 mil de lucro incremental (IC de 84 a 232 mil), contra
₽ 59 mil mandando para a base inteira, com 30 mil contatos em vez de 200 mil.

## O que o teste mostrou

1. A campanha funciona, mas o efeito é pequeno perto da base. A taxa de compra foi de 60,3%
   no controle para 63,7% em quem recebeu: +3,3 p.p. (IC 95% de 2,9 a 3,7), ou cerca de
   3.300 compradores a mais a cada 100 mil contatos. De cada 100 compras de quem recebeu a
   mensagem, 95 teriam acontecido sem ela.
2. O efeito muda muito de um cliente para outro. Nos 10% que menos gastavam, a campanha somou
   7,2 p.p.; nos 10% que mais gastavam, cerca de 1 p.p. Mudam de comportamento os clientes
   que compram menos, estão há mais dias sem comprar e são mais velhos (mediana de 58 anos
   contra 40).
3. Escolher os melhores clientes é o erro mais caro. Ordenar por chance de compra, o critério
   usual, põe no topo quem compra mais de 95% das vezes de qualquer jeito. Nos 30% escolhidos
   assim o efeito é de 1,9 p.p., abaixo do envio aleatório. O modelo de uplift encontra 5,4
   p.p. nos 30% que escolhe.

## Quanto vale

| | Mandar para todos | Uplift, 15% da base |
|---|---:|---:|
| Contatos | 200 mil | 30 mil |
| Compradores a mais | 6.650 (IC 4.790 a 8.650) | 2.520 (IC 1.750 a 3.250) |
| Custo dos contatos | ₽ 600 mil | ₽ 90 mil |
| Lucro incremental | ₽ 59 mil | ₽ 160 mil (IC 84 a 232 mil) |

Premissas: ₽ 3 por contato, ticket de ₽ 496 (média histórica), margem de 20% e uma compra
por comprador incremental. Com contato a ₽ 6, mandar para todos dá prejuízo de ₽ 541 mil,
enquanto os 10% de maior uplift ainda rendem ₽ 70 mil. Com contato a ₽ 1, ou a ₽ 3 com
margem de 30%, compensa mandar para todos. O simulador testa outras premissas.

## Riscos

- O modelo aprendeu com uma única comunicação, em março de 2019. Antes de escalar, vale
  repetir com um grupo de controle aleatório dentro do público escolhido, para medir o
  efeito real da seleção.
- O teste registrou se o cliente comprou, não quanto. A próxima rodada precisa medir ticket
  e gasto nos 30 dias seguintes, definidos antes do início, para garantir que a campanha não
  troca compras grandes por pequenas.
- Margem e custo são estimativas. A recomendação vale com contato a ₽ 3 e margem de até 20%,
  e com contato a partir de ₽ 6 em qualquer margem testada (15% a 30%).
- Todos os clientes do experimento tinham comprado nos 23 dias anteriores. Para inativos há
  mais tempo, este teste não diz nada.
