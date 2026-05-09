# Krono
## Whitepaper v0.6

**A bolsa de tempo humano**

---

## Resumo

Krono é uma bolsa onde pessoas emitem contratos de tempo futuro, o mercado precifica esses contratos por meio de transações, e a liquidação conecta organicamente ao mercado de trabalho. O primitivo central — o contrato de tempo — é estruturado como um futuro: ativo, quantidade e vencimento. Essa estrutura suporta mercado primário, mercado secundário, curva de prazo por emissor, rolagem condicionada à emissão contínua, e uma camada de gestão de posição onde o emissor administra ativamente sua estrutura de passivo — exatamente como uma tesouraria corporativa faz com dívida.

---

## 1. O Problema

O mercado de trabalho é estruturalmente opaco e assimétrico.

O valor do tempo humano é negociado de forma privada, sem referência de mercado verificável. Empregadores têm mais informação que trabalhadores. Pesquisas salariais agregam dados já obsoletos. Não existe mecanismo que precifique continuamente o tempo de um indivíduo específico com base em demanda real.

O resultado é ineficiência generalizada: pessoas subprecificam seu tempo, empregadores superpagam ou subpagam sem referência, e capital humano circula sem mecanismo de descoberta de preço.

Mercados financeiros resolveram esse problema para ativos tangíveis. Krono resolve para tempo humano.

---

## 2. A Solução

### 2.1 Identidade Verificada

O contrato de tempo é lastreado em uma pessoa real. Identidade verificada não é um detalhe de compliance — é o primitivo que torna o instrumento financeiramente válido.

Sem identidade verificada:
- O contrato não tem lastro — pode ser emitido por fantasma
- O score de honramento não tem valor — default sem consequência, nova identidade, recomeço
- A liquidação não tem garantia — não há como confirmar quem prestou o serviço

Com identidade verificada, o contrato de tempo se torna um instrumento real: o emissor é identificável, rastreável, e responsável pelo cumprimento. O histórico de honramentos acumula sobre uma identidade persistente e intransferível.

**Verificação é obrigatória para emitir, comprar e transacionar contratos em Krono.**

A identidade verificada do emissor é o único colateral do sistema — e é inseparável do ativo negociado.

### 2.2 O Contrato de Tempo

O primitivo central de Krono é o **contrato de tempo** — um instrumento estruturado como futuro, definido por três dimensões:

```
CONTRATO DE TEMPO

Ativo            → tempo do emissor (identidade verificada)
Quantidade       → n horas inteiras
Vencimento       → data de liquidação
Tipo             → FIXO ou MERCADO
```

Gerado automaticamente pela bolsa:

```
Titular atual    → detentor atual do contrato
Preço de mercado → R$/hora, atualizado por transações
Score do emissor → histórico de honramentos
```

A combinação **ativo + quantidade + vencimento** é o que define e padroniza cada contrato — exatamente como em mercados de futuros de commodities. Essa padronização é o que torna o mercado secundário possível: contratos com mesmo emissor e mesmo vencimento são intercambiáveis.

**Múltiplas séries simultâneas**

Um emissor pode ter contratos com vencimentos diferentes abertos ao mesmo tempo — por exemplo, Março/26, Junho/26 e Setembro/26. Cada série tem seu próprio preço de mercado, formando uma **curva de prazo** do tempo do emissor: o mercado precifica não apenas o valor presente do seu tempo, mas a expectativa de valorização ao longo do tempo.

Essa curva de prazo é um dado que não existe em nenhum sistema atual de precificação de trabalho humano.

### 2.3 Tipos de Contrato

Krono oferece dois instrumentos distintos dentro da mesma estrutura:

**Contrato Fixo**

O preço de recompra é travado no momento da emissão. O emissor sabe exatamente o que deve no vencimento independentemente de como seu preço de mercado evoluiu. É um instrumento de crédito pessoal — previsível, de menor risco para ambas as partes.

Do ponto de vista do payoff:
- Se o emissor valorizou, o detentor recebe o valor fixado — abaixo do mercado. O emissor captura o diferencial.
- Se o emissor desvalorizou, o detentor recebe o valor fixado — acima do mercado. O detentor captura o diferencial.

O Fixo é análogo a uma dívida prefixada: o emissor trava o custo do capital hoje, apostando que vai valorizar mais do que o preço travado.

**Contrato a Mercado**

O preço de recompra é o preço de mercado na data de vencimento. O comprador está essencialmente comprado na trajetória do emissor — com upside e downside reais.

Do ponto de vista do payoff, o contrato a Mercado tem assimetria semelhante a uma opção: se o emissor valorizar significativamente, o comprador lucra proporcionalmente; se desvalorizar, o comprador perde limitado ao capital investido. O emissor, por sua vez, tem exposição inversa — aceita pagar o preço que o mercado determinar no futuro.

Emitir contratos a Mercado é um sinal de confiança na própria trajetória: o emissor está dizendo ao mercado que aceita pagar o preço que o mercado determinar no futuro.

**A escolha como sinal**

A composição entre Fixo e Mercado na carteira de um emissor é informação pública e interpretável. Um emissor que emite majoritariamente a Mercado sinaliza confiança na própria valorização. Um emissor que emite majoritariamente Fixo pode estar buscando previsibilidade ou protegendo-se de downside — ambas as leituras são válidas e o mercado as processa.

### 2.4 Liquidação no Vencimento

No vencimento, a bolsa executa a liquidação automaticamente — sem necessidade de ação das partes.

**Fluxo automático:**

```
Série vence
    ↓
Para cada posição:
    debita emissor    → valor = preço × horas
    credita titular   → mesmo valor
    registra transação de liquidação
    ↓
    Existe série seguinte do mesmo emissor disponível?

    SIM → Rolagem automática
          debita titular  → preço série seguinte × horas
          credita emissor → mesmo valor
          registra transação de compra
          registra roll vinculando as duas séries
          titular mantém a mesma quantidade de horas no próximo vencimento

    NÃO → Liquidação final
          titular fica com saldo em dinheiro
```

**O spread de rolagem é resolvido via saldo:**

- Série seguinte mais cara → titular paga o diferencial do próprio saldo. Prejuízo.
- Série seguinte mais barata → titular recebe o diferencial no saldo. Lucro.

O emissor participa dos dois lados quando há rolagem: paga a liquidação da série que vence e recebe o valor da venda da série seguinte. O saldo líquido do emissor depende do spread entre os dois preços.

**Casos especiais:**

- **Emissor é o próprio titular** — débito e crédito no mesmo saldo, líquido zero. A transação existe no histórico mas não move dinheiro real.
- **Série vai para `LIQUIDATED`** se o saldo do emissor ficou >= 0 após a liquidação. Vai para `EXPIRED` se ficou negativo — juros correm sobre o saldo devedor.

---

## 3. Mecanismos de Mercado

### 3.1 Descoberta de Preço

O valor do tempo de cada pessoa não é definido por métrica externa — é descoberto pelo mercado. Cada transação é informação pública que atualiza o preço. Uma pessoa desconhecida que emite seus primeiros contratos a preço baixo já tem um preço de mercado a partir do primeiro comprador.

Isso é análogo ao funcionamento de uma bolsa de valores: o preço emerge do comportamento agregado dos participantes, não de uma fórmula.

### 3.2 Curva de Prazo

O conjunto de preços de mercado das séries abertas de um emissor forma sua curva de prazo — a estrutura temporal de precificação do seu tempo.

Uma curva ascendente indica que o mercado espera valorização futura. Uma curva plana indica estabilidade esperada. Uma curva invertida — vencimentos longos mais baratos que os curtos — pode indicar incerteza sobre trajetória ou risco percebido de desvalorização.

A curva de prazo é um dado público, contínuo e formado por demanda real. É a primeira vez que esse tipo de informação existe para trabalho humano.

### 3.3 Rolagem Automática

A rolagem não é uma decisão do titular — é executada automaticamente pela bolsa no vencimento, como consequência direta da decisão de emissão do emissor.

**A condição é objetiva:** se o emissor tem série com vencimento posterior disponível no mercado, a bolsa rola automaticamente todas as posições dos titulares para a série seguinte. Se o emissor não emitiu contratos futuros, não há para onde rolar — a liquidação em dinheiro é final.

Isso significa que a decisão de continuar ou encerrar a presença no mercado pertence inteiramente ao emissor. O emissor que quer manter contratos circulando emite novos vencimentos continuamente. O emissor que quer encerrar sua exposição simplesmente para de emitir — e no último vencimento, todos os titulares recebem liquidação em dinheiro.

**O spread de rolagem**

Quando a rolagem ocorre, o spread entre o preço da série que venceu e o preço da série seguinte é resolvido automaticamente via saldo:

- **Spread positivo** (próximo vencimento mais caro) — o titular paga o diferencial do próprio saldo. O mercado precifica valorização esperada do emissor no período.
- **Spread negativo** (próximo vencimento mais barato) — o titular recebe crédito no saldo. O mercado precifica desvalorização esperada ou incerteza.

Esse mecanismo é análogo ao *contango* e *backwardation* em mercados de commodities — aplicado à trajetória de carreira humana.

**O emissor nos dois lados**

Quando há rolagem, o emissor participa simultaneamente da liquidação da série que vence e da venda da série seguinte. O saldo líquido do emissor depende do spread: se a série seguinte é mais cara, o emissor recebe mais do que paga; se mais barata, recebe menos.

**Prêmio de continuidade**

A decisão de parar de emitir é um sinal público e interpretável pelo mercado. Titulares de contratos de um emissor que parou de emitir sabem que não haverá rolagem disponível no vencimento — e precificam isso, provavelmente exigindo desconto para segurar o contrato até a liquidação final.

O inverso também é verdadeiro: emissores que mantêm séries abertas de forma consistente têm contratos mais líquidos e potencialmente mais valorizados. A emissão contínua é um compromisso de mercado — e o mercado recompensa esse compromisso com liquidez.

**O spread como sinal independente**

Um emissor com spread consistentemente positivo ao longo do tempo — o mercado sempre precifica o próximo vencimento mais caro — é um emissor com trajetória de valorização esperada sustentada. Esse sinal é público, contínuo, e formado por agentes com capital em risco: é informação de qualidade superior à de qualquer pesquisa salarial ou avaliação de desempenho subjetiva.

### 3.4 Mercado Secundário

Contratos podem ser revendidos antes do vencimento. A padronização por quantidade e vencimento é o que torna o mercado secundário líquido: contratos com mesmo emissor e mesmo vencimento são fungíveis entre si.

Um comprador no mercado secundário pode ter dois perfis distintos — e ambos são igualmente previstos pelo design da bolsa:

**Comprador especulativo** — acredita que o emissor vai valorizar até o vencimento. Compra com intenção de revender mais caro ou receber a liquidação financeira acima do preço pago.

**Comprador utilitário** — precisa das horas do emissor e o mercado primário está esgotado. Adquire o contrato para exercê-lo no vencimento, recebendo o serviço diretamente.

Essa dualidade é estrutural: o mercado secundário funciona simultaneamente como mecanismo de especulação e como mecanismo de alocação de serviço. Contratos emitidos por emissores com alta demanda real tendem a migrar naturalmente para detentores utilitários conforme o vencimento se aproxima — o que adiciona liquidez e sustenta o preço.

### 3.5 Score de Honramento

Cada liquidação é registrada publicamente associada à identidade do emissor. O histórico de honramentos é o que constrói reputação de forma objetiva e alimenta a precificação futura. Sem histórico, não há mercado secundário líquido.

### 3.6 Mercado de Seguro

O risco de default mensurável cria naturalmente um mercado de seguro. Compradores podem contratar proteção contra não-liquidação. O prêmio do seguro é função do score de honramento do emissor — quanto mais confiável, mais barato o seguro.

---

## 4. Gestão de Posição pelo Emissor

O emissor não é apenas quem emite e quem deve — é um participante ativo do mercado do próprio tempo. A composição da sua carteira de contratos, a proporção entre Fixo e Mercado, os vencimentos escolhidos, e a decisão de reter ou vender contratos próprios formam uma **estrutura de passivo** que o emissor administra ativamente — exatamente como tesourarias corporativas gerenciam dívida.

### 4.1 Carteira Própria

O emissor pode emitir contratos e reter parte deles em carteira própria em vez de vender tudo no mercado. Com esses contratos em mão, pode:

- **Vender gradualmente** conforme precisa de capital — gestão de fluxo de caixa do próprio tempo
- **Usar para equilibrar obrigações** entre vencimentos — contratos próprios retidos podem ser vendidos para financiar recompras em outros vencimentos
- **Sinalizar confiança** — reter contratos próprios é estar comprado em si mesmo. Se valorizar, os contratos retidos valem mais. O emissor captura o upside da própria valorização.

### 4.2 Arbitragem entre Fixo e Mercado

O emissor que administra ativamente sua estrutura de passivo pode montar estratégias entre os dois tipos de contrato.

**Exemplo:** o emissor emite contratos Fixo a R$100/hora e posteriormente valoriza para R$150/hora. No vencimento, liquida o Fixo a R$100 — abaixo do mercado — capturando R$50/hora de diferencial. Esse diferencial pode ser usado para financiar a liquidação de contratos a Mercado emitidos no mesmo período, que vencem a R$150.

O resultado é uma estrutura onde contratos Fixo emitidos com convicção de valorização financiam o custo dos contratos a Mercado — gestão ativa de passivo usando os próprios instrumentos da bolsa.

### 4.3 A Composição como Sinal

A estrutura de passivo do emissor — quanto é Fixo, quanto é Mercado, quais vencimentos, quanto retém em carteira própria, se mantém emissão contínua ou emite esporadicamente — é pública e interpretável pelo mercado:

- **Maioria a Mercado** → emissor confia na própria valorização e aceita pagar o preço futuro
- **Maioria Fixo** → emissor busca previsibilidade ou está protegendo downside
- **Grande carteira própria** → emissor está comprado em si mesmo, alinhando seu interesse ao do mercado
- **Emissão contínua** → compromisso de manter presença no mercado, sinal de estabilidade e liquidez
- **Emissão esporádica ou encerrada** → sinal de retirada, detentores precificam ausência de rolagem futura

Nenhum desses sinais é definitivo — o mercado os interpreta em conjunto com preço, curva de prazo, spread de rolagem e score de honramento. O resultado é um perfil financeiro completo de cada emissor, formado por comportamento real com capital em risco, não por autodeclaração.

---

## 5. O Vínculo Empregatício como Posição Financeira

O mercado de trabalho tradicional é uma relação opaca: salário negociado privadamente, renegociação é conflito, saída é ruptura. O preço do tempo do trabalhador não existe publicamente — é estimado, inferido, disputado.

Krono transforma essa relação em uma posição financeira gerenciada por ambos os lados.

### 5.1 O Empregador como Investidor

Quando um empregador contrata via Krono, ele não paga salário mensal — ele compra horas futuras a preço atual. Isso muda a natureza do vínculo.

O empregador que compra horas de alguém com potencial de valorização está fazendo um investimento: trava o custo presente, captura o upside futuro. Se o funcionário valorizar, o empregador tem duas opções:

- **Manter a posição** — continua com acesso ao tempo do funcionário ao preço travado, mesmo que o mercado o precifique mais alto
- **Vender parte das horas** no mercado secundário com lucro

A curva de prazo, o spread de rolagem e a estrutura de passivo do funcionário viram informação de investimento: o empregador pode ler a expectativa de mercado sobre a trajetória do funcionário antes de decidir em quais vencimentos e tipos concentrar posição.

Isso cria um incentivo estrutural que o mercado de trabalho tradicional não consegue replicar: o empregador tem interesse genuíno no desenvolvimento do funcionário, porque valorização do ativo beneficia o detentor.

### 5.2 O Funcionário com Autonomia Precificada

Do lado do funcionário, autonomia tem um custo explícito e transparente: recomprar as horas vendidas ao preço de mercado vigente.

Se o funcionário valorizou desde a emissão, recompra mais caro — o empregador captura esse diferencial. Se desvalorizou, recompra mais barato. Em ambos os casos, o preço é público, verificável, e não negociado em conflito.

Isso inverte a assimetria atual: o funcionário sabe exatamente o custo de sair antes de sair. A decisão de autonomia vira uma decisão financeira calculável, não uma ruptura emocional.

### 5.3 Saída como Transação, não Ruptura

Com Krono, saída é uma transação de mercado:

- **Funcionário quer sair** — recompra as horas detidas pelo empregador ao preço de mercado. O empregador recebe o valor justo, o funcionário recupera sua posição.
- **Empregador quer encerrar** — vende as horas no mercado secundário ou aceita recompra pelo emissor. O vínculo se dissolve via transação, não via conflito.

O histórico de honramentos de ambos os lados é público. Empregadores que vendem posições prematuramente sem justificativa acumulam reputação negativa — o que cria pressão de mercado contra comportamento oportunista.

### 5.4 O Loop de Valorização

As dinâmicas acima se reforçam mutuamente:

> Empregador compra horas e investe no desenvolvimento → funcionário valoriza → curva de prazo sobe, spread de rolagem aumenta → empregador captura upside ou trava custo favorável → funcionário com histórico de valorização atrai novos compradores → preço de mercado sobe → poder de barganha aumenta → próxima emissão parte de uma base mais alta

O resultado é um mercado onde empregador e funcionário têm interesse conjunto na valorização — alinhamento de incentivos que contratos de trabalho tradicionais tentam criar artificialmente via bônus e participação em resultados, sem conseguir precificar o ativo subjacente.

---

## 6. Estrutura da Bolsa

Krono opera como bolsa, não como plataforma de serviços. Isso significa que Krono:

- **Padroniza** os contratos por ativo, quantidade e vencimento
- **Registra** todas as transações publicamente
- **Verifica disponibilidade de vencimentos** para determinar se rolagem é possível
- **Garante o ambiente** para que contratos sejam executados entre as partes
- **Arbitra disputas** de liquidação via câmara de compensação

Krono não executa os contratos diretamente — as partes executam. A câmara cuida do risco de default, como ocorre em bolsas de commodities onde a entrega física também é feita fora da plataforma.

A bolsa registra apenas eventos financeiros verificáveis: emissões, transações, recompras, rolagens. O que ocorre fora — o serviço prestado, o desenvolvimento do funcionário, a negociação entre as partes — é informação de mercado, não responsabilidade da bolsa.

---

## 7. Fracionamento

A unidade mínima de contrato é a hora inteira. Fracionamento em unidades menores é uma decisão em aberto — a ser determinada pela dinâmica de mercado após lançamento.

---

## 8. Posicionamento

| Mercado | Ativo | Estrutura | Referência |
|---|---|---|---|
| Bolsa de valores | Equity de empresas | Spot | NYSE, B3 |
| Bolsa de commodities | Ativos físicos padronizados | Futuros | CME, B3 |
| Mercados preditivos | Eventos futuros | Binário | Polymarket, IEM |
| **Krono** | **Tempo humano futuro** | **Futuros** | — |

Cada bolsa formalizou um mercado que antes era informal, opaco e ineficiente. Krono faz o mesmo para o tempo humano — com a propriedade única de que o ativo negociado é inseparável do emissor, o que elimina o risco de colateral evaporar e cria alinhamento de incentivos estrutural entre todas as partes.

---

## 9. Estratégia de Lançamento

O modelo não pressupõe casos de uso. Krono oferece o primitivo — o contrato de tempo estruturado como futuro — e o mercado descobre os usos.

A adoção tende a seguir a curva histórica das bolsas: começa com emissores que já têm demanda comprovada pelo seu tempo (profissionais estabelecidos, criadores com audiência), o mercado ganha liquidez e mecanismos de precificação, e então pessoas sem histórico passam a ter referência de valor e compradores dispostos a apostar em trajetórias emergentes.

O caso de uso empregatício acelera esse processo: empregadores que adotam Krono como forma de contratação trazem liquidez imediata ao mercado e geram dados de precificação reais — incluindo curvas de prazo, spreads de rolagem e estruturas de passivo — que beneficiam todos os participantes subsequentes.

A interface não pressupõe perfil de emissor. Qualquer pessoa pode emitir. O mercado determina se há compradores.

---

## 10. Questões em Aberto

As seguintes decisões serão informadas pela dinâmica de mercado pós-lançamento:

- Fracionamento de contratos
- Padronização de vencimentos: datas fixas (trimestral, semestral) ou livres por emissor
- Faixa mínima de spread para contratos fixos
- Definição do protocolo de arbitragem da câmara de compensação

---

*Krono — v0.7 — documento em evolução*
