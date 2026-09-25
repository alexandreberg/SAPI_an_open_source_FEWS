# BOM de Custos — Hardware SAPI

Levantamento de custos por hardware do SAPI, para citação na dissertação (fornecedor + preço + data de consulta). Relacionado à issue #173.

**Hardware/eletrônica da Estação-01 (BluePill/F103C8T6) fica de fora** deste levantamento — mesmo precedente do capítulo de Produtos Técnico-Tecnológicos (PTT) da qualificação, que não trata o MCU descontinuado como produto-alvo. A **estrutura física/ferragem de fixação da Estação-01 é contabilizada** (ver seção própria), pois pode ser reaproveitada para hospedar hardware novo (tipo Estação-03) caso essa estação seja futuramente atualizada.

## Metodologia

- **Preço unit.** = (preço do item + imposto de importação) ÷ quantidade da embalagem, quando o anúncio vende em lote/multipack. O imposto é somado porque escala com o valor declarado independentemente de consolidação de pedido — ao contrário do frete, ele não dilui quando vários itens são comprados juntos.
- **Frete propositalmente excluído** do preço unitário e do subtotal de cada linha, salvo exceção explícita — ver [nota sobre frete](#nota-sobre-frete).
- **Fonte**: AliExpress (salvo indicação contrária — Mercado Livre ou JLCPCB são citados por linha). Preços capturados/informados em 2026-07-07.
- Colunas **Link** e **Data** foram removidas da planilha por pedido — o essencial para citação (fornecedor + valor) já está registrado; link de produto fica pendente de recuperação posterior se necessário.
- Capacitores cerâmicos (disco, qualquer valor 0,1–10 µF) usam o mesmo kit de 500 peças / 10 valores como fonte de preço em ambas as tabelas.
- **Cotação USD→BRL usada: R$5,16 (dólar paralelo, 2026-07-07)** — aplicada apenas à linha de PCB (JLCPCB), único item cotado em dólar.
- Fios e cabos soltos/genéricos não são contabilizados nesta planilha (decisão do autor), exceto onde um cabo específico foi explicitamente precificado (ex.: cabo manga externo, cabos internos dupont, cabinho flexível 22AWG).

---

## Tabela 1 — SAPI Shield Morpho V1.2

`hardware/morpho-shield-v1.2/`

| Ref. | Item | Qtd | Fornecedor | Preço unit. | Subtotal |
|---|---|---|---|---|---|
| C1,C2,C3,C4,C5,C7,C8 | Capacitor disco 1uF | 7 | AliExpress (kit 500pçs/10 valores 0,1–10uF) | R$0,063 | R$0,44 |
| C6,C9 | Capacitor disco 0.1uF | 2 | AliExpress (idem) | R$0,063 | R$0,13 |
| D1,D2 | Diodo Schottky SS36 (SMD) | 2 | AliExpress (Elecset Tech Store, kit 150pçs/15 valores) | R$0,212 | R$0,42 |
| J1,J2 | Soquete Morpho 2×19 (conecta no Nucleo) | 2 | AliExpress (alinsin Store, conector 2×40 fêmea reto) | R$2,09 | R$4,18 |
| J3 | Borne Phoenix 2 vias (pluviômetro) | 1 | AliExpress (alinsin Store) | R$1,61 | R$1,61 |
| J5,J6 | Borne Phoenix 2 vias (+12V/+20V) | 2 | AliExpress (alinsin Store) | R$1,61 | R$3,23 |
| J7 | Header 1×05 horizontal | 1 | AliExpress (header macho 1×40, rateado por pino) | R$0,17 | R$0,17 |
| J8 | Header 1×06 (STLINK) | 1 | AliExpress (idem) | R$0,20 | R$0,20 |
| J9 | Header 1×05 vertical | 1 | AliExpress (idem) | R$0,17 | R$0,17 |
| J10 | Header 1×02 (UART) | 1 | AliExpress (idem) | R$0,07 | R$0,07 |
| J11 | Header 1×02 vertical | 1 | AliExpress (idem) | R$0,07 | R$0,07 |
| US1 | Header 1×05 (sensor ultrassônico) | 1 | AliExpress (idem) | R$0,17 | R$0,17 |
| JP1,JP2,JP6,JP7 | Jumper 3 pinos SPDT | 4 | AliExpress (kit 100un) | R$0,09 | R$0,35 |
| JP3,JP4,JP8,JP9,JP10,JP11,JP12 | Jumper/header 2 pinos | 7 | AliExpress (header macho 1×40, rateado por pino) | R$0,07 | R$0,48 |
| JP5 | Solder jumper 3 vias | 1 | (pad na placa, sem peça) | — | — |
| R1 | Resistor 470R | 1 | AliExpress (kit 2600pçs/130 valores 1/4W 1%) | R$0,028 | R$0,03 |
| R2,R3 | Resistor 10k | 2 | AliExpress (idem) | R$0,028 | R$0,06 |
| R4 | Resistor 470k | 1 | AliExpress (idem) | R$0,028 | R$0,03 |
| R5 | Resistor 150k | 1 | AliExpress (idem) | R$0,028 | R$0,03 |
| R6 | Resistor 680k | 1 | AliExpress (idem) | R$0,028 | R$0,03 |
| R7 | Resistor 100k | 1 | AliExpress (idem) | R$0,028 | R$0,03 |
| H1,H2,H3 | Parafuso/furo de montagem M3 12mm | 3 | AliExpress (kit 100pçs, aço preto, cabeça panela phillips) | R$0,144 | R$0,43 |
| U1 | Optoacoplador TIL113 (DIP-6) | 1 | AliExpress (KUNYO Xinsheng Excellence Technology Store) | R$1,87 | R$1,87 |
| U2 | CD4040 — contador binário 12 estágios (DIP-16) | 1 | AliExpress (Supplier of electronic components Store) | R$1,10 | R$1,10 |
| U3 | 74HC166 — registrador de deslocamento 8 bits (DIP-16) | 1 | AliExpress (kit 10un) | R$0,95 | R$0,95 |
| U4 | Header 1×04 2,54mm (conector p/ módulo de temperatura — sensor varia por estação, ver Estação-02) | 1 | AliExpress (header macho 1×40, rateado por pino) | R$0,14 | R$0,14 |
| U5,U6,U7 | Módulo chave MOSFET HW-613 | 3 | AliExpress (Gangda Tong Store — preço do módulo DC-DC step-down usado como proxy, ver nota¹) | R$3,10 | R$9,30 |
| U1 (soquete, opcional) | Soquete IC DIP-6 para U1 | 1 | AliExpress (alinsin Store, kit 10un) | R$0,75 | R$0,75 |
| U2,U3 (soquete, opcional) | Soquete IC DIP-16 para U2/U3 | 2 | AliExpress (alinsin Store, kit 10un) | R$1,13 | R$2,26 |
| — | PCB (fabricação, JLCPCB) | 1 | JLCPCB (pedido combinado com Tabela 2, ver nota²; US$3,52 × R$5,16) | R$18,19 | R$18,19 |
| **Total** | | | | | **R$46,89** |

¹ O anúncio localizado para U5–U7 é um módulo DC-DC step-down 12-24V→5V (20 unidades), não o HW-613 exato — usado como estimativa por instrução direta; confirmar peça exata depois.
² Ver nota sobre PCB abaixo da Tabela 2.

> **U4**: o módulo de sensor de temperatura (ex. BMP280) não é item fixo do shield — apenas o header 2,54mm fica na placa. A definição do sensor varia por estação; na Estação-02 é o BMP280 (precificado na tabela própria, abaixo).

> Soquetes DIP são opcionais (não são Ref. do schematic — facilitam retrabalho no lugar de solda direta de U1/U2/U3), mas já entram no Total acima por terem sido incluídos como linhas.

## Tabela 2 — SAPI LoRa Arduino Shield V1.0

`hardware/lora-arduino-shield-v1.0/`

| Ref. | Item | Qtd | Fornecedor | Preço unit. | Subtotal |
|---|---|---|---|---|---|
| C1 | Capacitor disco 100nF | 1 | AliExpress (kit 500pçs/10 valores 0,1–10uF) | R$0,063 | R$0,06 |
| D2 | LED 3mm | 1 | AliExpress (kit 1000un) | R$0,046 | R$0,05 |
| J1 | Header 1×08 (Power) | 1 | AliExpress (header macho 1×40, rateado por pino) | R$0,27 | R$0,27 |
| J2 | Header 1×10 (Digital/PWM) | 1 | AliExpress (idem) | R$0,34 | R$0,34 |
| J3 | Header 1×06 (Analog) | 1 | AliExpress (idem) | R$0,20 | R$0,20 |
| J4 | Header 1×08 (Digital/PWM) | 1 | AliExpress (idem) | R$0,27 | R$0,27 |
| J7 | Header 1×05 horizontal (Power) | 1 | AliExpress (idem) | R$0,17 | R$0,17 |
| JP1–JP4 | Jumper 3 pinos SPDT | 4 | AliExpress (kit 100un) | R$0,09 | R$0,35 |
| JP11,JP12 | Header/jumper 2 pinos | 2 | AliExpress (header macho 1×40, rateado por pino) | R$0,07 | R$0,14 |
| R7 | Resistor 10k | 1 | AliExpress (kit 2600pçs/130 valores 1/4W 1%) | R$0,028 | R$0,03 |
| S1 | Botão tátil 6×6mm | 1 | AliExpress (kit 100un) | R$0,32 | R$0,32 |
| SW4 | Chave DPDT push (reset) | 1 | AliExpress (kit 100un — frete incluído por exceção, ver nota sobre frete) | R$0,31 | R$0,31 |
| U4 **ou** U8 | Módulo rádio: **LILYGO LoRa32 (escolhido — opção mais cara das duas alternativas)** | 1 | AliExpress (lilygo Official Store — "LILYGO® TTGO Accessories Shield LoRa 868/915Mhz") | R$104,04 | R$104,04 |
| — | PCB (fabricação, JLCPCB) | 1 | JLCPCB (pedido combinado com Tabela 1, ver nota²; US$3,52 × R$5,16) | R$18,19 | R$18,19 |
| **Total** | | | | | **R$124,74** |

> **AE1 (antena LoRa 915MHz) removida** da tabela — já vem embutida no módulo de rádio (LILYGO LoRa32), não é item separado.

> **Nota sobre PCB**: fabricação combinada das duas placas na JLCPCB, 5 unidades de cada shield, total US$18,55 + 90% de impostos = US$35,25 para as 10 placas → US$3,5245/placa → **R$18,19/placa** (câmbio R$5,16/US$, dólar paralelo, 2026-07-07), aplicado como Preço unit. em ambas as tabelas (Qtd 1 = uma placa por shield).

---

## Itens de Inventário Manual — por Estação

Estação-02 = pluviométrica (báscula), Estação-03 = cota de nível. Cada uma soma seu próprio MCU + fonte de energia + rádio + case/estrutura; itens abaixo não incluem o custo das placas Shield Morpho/LoRa (Tabelas 1 e 2 — uma de cada por estação).

### Estação-02 (pluviométrica)

| Item | Fornecedor | Preço unit. | Qtd | Subtotal |
|---|---|---|---|---|
| NUCLEO-F103RB STM32 Nucleo-64 | AliExpress (frete incluído por exceção — ver nota) | R$189,11 | 1 | R$189,11 |
| Módulo BMP280 (breakout HW-611, temperatura/pressão) | AliExpress (kit 5un) | R$3,77 | 1 | R$3,77 |
| Controlador de Carga Morningstar Sunkeeper 6A 100W | Mercado Livre (já com imposto+frete) | R$74,00 | 1 | R$74,00 |
| Bateria VRLA 12V 2,3Ah Xb 1223 (Intelbras, ~2200mAh) | Mercado Livre (já com imposto+frete) | R$137,26 | 1 | R$137,26 |
| Pluviômetro de báscula digital PB10 | Mercado Livre (Usinainfo — frete somado por exceção, ver nota) | R$952,62 | 1 | R$952,62 |
| Interruptor rocker KCD1-110 (seletor V painel / V bateria) | AliExpress (xin cheng electronic — assumido pacote de 10un*) | R$2,17 | 2 | R$4,34 |
| Painel Solar Ztroon 20W Fotovoltaico Monocristalino PERC¹ | Mercado Livre (já com imposto+frete) | R$126,00 | 1 | R$126,00 |
| Abrigo meteorológico para sensores TPH | AliExpress (78,00 + 16,00 imp + 41,28 frete somado por exceção) | R$135,28 | 1 | R$135,28 |
| Filamento PETG XT Branco 1,75mm (partes internas/suportes)² | 3dfila.com.br (já com imposto+frete) | R$96,90/kg × 1,5kg | 1,5kg | R$145,35 |
| Tubo PVC Esgoto 100mm Amanco (50cm, de barra de 6m R$119,90) | Loja física/local (já com imposto+frete) | R$19,983/m | 0,5m | R$9,99 |
| Cap PVC Esgoto 100mm Amanco | Loja física/local (já com imposto+frete) | R$9,60 | 1 | R$9,60 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (suporte bateria interna) | Loja física/local | R$0,27/un (0,16+0,11) | 4 | R$1,08 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (prendedor da tampa do case) | Loja física/local | R$0,27/un | 4 | R$1,08 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (controlador de carga) | Loja física/local | R$0,27/un | 2 | R$0,54 |
| Parafuso Phillips Máquina Panela MA 3×30 Inox + porca sextavada (suporte do case) | Loja física/local | R$0,87/un (0,76+0,11) | 6 | R$5,22 |
| Parafuso Phillips Máquina Panela MA 3×20 Inox + porca sextavada (suporte do case) | Loja física/local | R$0,60/un (0,49+0,11) | 4 | R$2,40 |
| Parafuso Phillips Máquina Panela MA 3×30 Inox + porca sextavada (trava da placa Nucleo) | Loja física/local | R$0,87/un | 1 | R$0,87 |
| Auto Atarraxante Phillips Chata 2.2×6,5 Aço Carbono Zincado (presilhas da tampa) | Loja física/local | R$0,05/un | 8 | R$0,40 |
| Auto Atarraxante Phillips Panela 2.2×13 Aço Carbono Zincado (colunas/standoffs) | Loja física/local | R$0,06/un | 40 | R$2,40 |
| Conector painel GX12 2 pinos (par macho+fêmea) | AliExpress (Widsey Store, kit 5un) | R$5,14 | 1 | R$5,14 |
| Conector painel GX12 5 pinos (par macho+fêmea) | AliExpress (Widsey Store, kit 5un) | R$5,65 | 2 | R$11,31 |
| Push-button de reset geral (tampa do case) | AliExpress (TLZWLA Official Store) | R$8,97 | 1 | R$8,97 |
| Cabo dupont fêmea-fêmea 2,54mm 5pin 50cm (conexão interna entre placas) | AliExpress (Electrical Wire Store, kit 10un) | R$5,56 | 4 | R$22,26 |
| Cabinho flexível eletrônica 22AWG (0,30mm), várias cores — fiação interna (rolo 100m) | Mercado Livre (frete incluso) | R$0,60/m | 15m | R$9,00 |
| Abraçadeira Nylon Preto 50cm, resistente UV 30kg, modelo SQ-4280 (pacote 100un) | Mercado Livre (frete incluso) | R$0,331/un | 4 | R$1,32 |
| **Subtotal Estação-02 (itens manuais, exclui Shield Morpho/LoRa; exclui ferragem do post — ver seção própria)** | | | | **R$1.859,31** |

### Estação-03 (cota de nível)

| Item | Fornecedor | Preço unit. | Qtd | Subtotal |
|---|---|---|---|---|
| Nucleo L476RG | AliExpress (W Official Store) com frete incluso| R$245,78 | 1 | R$245,78 |
| EPEVER Tracer2606BP-10A/12V 24V Auto (MPPT) | AliExpress (Solar & Wind Store) | R$383,55 | 1 | R$383,55 |
| Bateria de lítio 12V 4400mAh c/ BMS Sanyo | Mercado Livre (já com imposto+frete) | R$94,04 | 1 | R$94,04 |
| SHT20 (IP65, Style A) | AliExpress (UICPAL Official Store) | R$55,64 | 1 | R$55,64 |
| US-100 (sensor ultrassônico, já em operação) | AliExpress (loja não especificada na cotação) | R$29,28 | 1 | R$29,28 |
| Interruptor rocker KCD1-110 (seletor V painel / V bateria) | AliExpress (xin cheng electronic — assumido pacote de 10un*) | R$2,17 | 2 | R$4,34 |
| Painel Solar Ztroon 20W Fotovoltaico Monocristalino PERC¹ | Mercado Livre (já com imposto+frete) | R$126,00 | 1 | R$126,00 |
| Abrigo meteorológico para sensores TPH | AliExpress (78,00 + 16,00 imp + 41,28 frete somado por exceção) | R$135,28 | 1 | R$135,28 |
| Filamento PETG XT Branco 1,75mm (partes internas/suportes)² | 3dfila.com.br | R$96,90/kg × 1,5kg | 1,5kg | R$145,35 |
| Tubo PVC Esgoto 100mm Amanco (50cm, de rolo de 6m R$119,90) | Loja física/local | R$19,983/m | 0,5m | R$9,99 |
| Cap PVC Esgoto 100mm Amanco | Loja física/local | R$9,60 | 1 | R$9,60 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (suporte bateria interna) | Loja física/local | R$0,27/un (0,16+0,11) | 4 | R$1,08 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (prendedor da tampa do case) | Loja física/local | R$0,27/un | 4 | R$1,08 |
| Parafuso Phillips Máquina Panela MA 3×16 Inox + porca sextavada (controlador de carga) | Loja física/local | R$0,27/un | 2 | R$0,54 |
| Parafuso Phillips Máquina Panela MA 3×30 Inox + porca sextavada (suporte do case) | Loja física/local | R$0,87/un (0,76+0,11) | 6 | R$5,22 |
| Parafuso Phillips Máquina Panela MA 3×20 Inox + porca sextavada (suporte do case) | Loja física/local | R$0,60/un (0,49+0,11) | 4 | R$2,40 |
| Parafuso Phillips Máquina Panela MA 3×30 Inox + porca sextavada (trava da placa Nucleo) | Loja física/local | R$0,87/un | 1 | R$0,87 |
| Parafuso Phillips Máquina Panela MA 3×20 Inox + porca sextavada (tampa da placa do sensor ultrassônico US-100) | Loja física/local | R$0,60/un | 4 | R$2,40 |
| Auto Atarraxante Phillips Chata 2.2×6,5 Aço Carbono Zincado (presilhas da tampa) | Loja física/local | R$0,05/un | 8 | R$0,40 |
| Auto Atarraxante Phillips Panela 2.2×13 Aço Carbono Zincado (colunas/standoffs) | Loja física/local | R$0,06/un | 40 | R$2,40 |
| Conector painel GX12 2 pinos (par macho+fêmea) | AliExpress (Widsey Store, kit 5un) | R$5,14 | 1 | R$5,14 |
| Conector painel GX12 5 pinos (par macho+fêmea) | AliExpress (Widsey Store, kit 5un) | R$5,65 | 2 | R$11,31 |
| Push-button de reset geral (tampa do case) | AliExpress (TLZWLA Official Store) | R$8,97 | 1 | R$8,97 |
| Cabo dupont fêmea-fêmea 2,54mm 5pin 50cm (conexão interna entre placas) | AliExpress (Electrical Wire Store, kit 10un) | R$5,56 | 4 | R$22,26 |
| Cabinho flexível eletrônica 22AWG (0,30mm), várias cores — fiação interna (rolo 100m) | Mercado Livre (frete incluso) | R$0,60/m | 15m | R$9,00 |
| **Subtotal Estação-03 (itens manuais, exclui Shield Morpho/LoRa; exclui ferragem — ver seção própria; régua e pluviômetro de copo NÃO entram aqui, são equipamento de calibração)** | | | | **R$1.311,92** |

¹ Especificações do painel Ztroon 20W: Pmax 20W, Vmp 21,25V, Imp 0,95A, Voc 24,72V, Isc 0,99A, eficiência 16,2%, célula monocristalina PERC (36 células, config. 4×9), 275×450×17mm, 0,12m², 1,25kg.
² Fonte: [3dfila.com.br/produto/filamento-petg-branco](https://3dfila.com.br/produto/filamento-petg-branco/). Preço por kg assumido a partir do rolo padrão de 1kg — confirmar peso do rolo anunciado antes de fechar a compra.
\* KCD1-110: (17,99 + 3,73 imp)/10 — pacote de 10 peças (preço corrigido pelo autor 2026-07-07).

**Custo estimado por estação completa** = Subtotal manual da estação + Tabela 1 (Shield Morpho, R$46,89) + Tabela 2 (Shield LoRa, R$124,74), já com PCB convertido para R$. **Estação-02 ≈ R$2.030,94. Estação-03 ≈ R$1.483,55.** Ambos **excluem** a ferragem do post/estrutura de fixação — ver [Resumo de Custos](#resumo-de-custos) e a seção de Ferragem por Estação, abaixo.

### Gateway

Sem case dedicado (impresso em PETG) — usa a mesma lógica de tubo/cap PVC das estações, em tamanho menor.

| Item | Fornecedor | Preço unit. | Qtd | Subtotal |
|---|---|---|---|---|
| LilyGo T-SIM7000G | AliExpress (lilygo Official Store) (já com imposto+frete) | R$395,51 | 1 | R$395,51 |
| Cap PVC Esgoto 100mm Amanco | Loja física/local (já com imposto+frete) | R$9,60 | 1 | R$9,60 |
| Tubo PVC Esgoto 100mm Amanco (40cm) | Loja física/local (já com imposto+frete) | R$19,983/m | 0,4m | R$7,99 |
| Filamento PETG XT Branco 1,75mm (case impresso) | 3dfila.com.br (já com imposto+frete) | R$96,90/kg | 1kg | R$96,90 |
| Cartão de memória microSD 32GB (SanDisk Ultra Classe 10, 100MB/s, c/ adaptador SD) | Mercado Livre (frete grátis) | R$49,51 | 1 | R$49,51 |
| Fonte de alimentação USB-C | Não especificado (frete+imposto inclusos) | R$40,00 | 1 | R$40,00 |
| **Subtotal Gateway (itens com preço; sem ferragem — Gateway é indoor, sem post)** | | | | **R$599,51** |

> **Chip M2M**: custo recorrente de R$10,00/mês (assinatura de dados) — não é item de BOM único, não entra no subtotal acima. Anotar à parte no orçamento operacional.

### Ferragem por Estação

**Fonte: Zinca Rápido Comércio de Ferragens, Orçamento #881518, 07/07/2026** (`/var/tmp/BOMlist/ferragens.jpeg`) — cobre parte da estrutura tubular da Estação-01 e da Estação-03. **Correção 2026-07-07**: "Ferragem E1" era mesmo **Estação-01** (não Estação-02, como assumido antes) — o hardware BluePill continua fora do escopo, mas essa estrutura é contabilizada por poder ser reaproveitada com eletrônica nova tipo Estação-03.

**Estação-01** (retrofit estrutural — post/braço de fixação na ponte; eletrônica reaproveitaria os valores já precificados na Estação-03 se essa substituição avançar):

| Item | Preço unit. (loja) | Observação |
|---|---|---|
| Conexão T 3/4" com rosca | R$15,91/un | 2 unidades necessárias → R$31,82 |
| Tubo de ferro galvanizado rosca 3/4" CH2,25mm (barra) | R$24,695/m (barra 6m R$148,17) | ~7m necessários → R$172,87 (custeado por metro, não por barra inteira) |
| Fonte de alimentação 12V 2A bivolt estabilizada (LED) | R$11,50/un | Mercado Livre, frete grátis |
| Barra Fe galvanizado 1½"×3/16" — corte 2×25cm+2×10cm (70cm) | R$12,848/m (barra 6m R$77,09) | Loja física/local |
| Barra Fe galvanizado 3/4"×3/16" — corte 6×15cm+4×5cm+100cm (210cm) | R$8,065/m (barra 6m R$48,39) | Loja física/local |
| **Subtotal parcial (2×T + tubo + fonte + barras)** | | **R$242,12** (31,82 + 172,87 + 11,50 + 8,99 + 16,94) |

**Estação-03** (adicional à ferragem já listada — 3m cano 3/4" + 1 joelho — e ao suporte do painel solar):

| Item | Preço unit. (loja) | Observação |
|---|---|---|
| Conexão cotovelo 90° fêmea 3/4" | R$12,44/un | Bate com a pendência "1 joelho 3/4"" |
| Tubo de ferro galvanizado rosca 3/4" (mesma barra da Estação-01) | R$24,695/m (barra 6m R$148,17) | ~3m necessários → R$74,09 (custeado por metro, não por barra inteira) |
| Barra Fe galvanizado 1½"×3/16" — corte 2×25cm (50cm) | R$12,848/m (barra 6m R$77,09) | Loja física/local |
| Barra chata Fe galvanizado 1/2"×1/8" — corte 4×50cm (suporte painel solar) | R$2,678/m (barra 6m R$16,07) | Loja física/local |
| **Subtotal parcial (cotovelo + tubo + barras)** | | **R$98,31** (12,44 + 74,09 + 6,42 + 5,36) |

**Compartilhado / uso ainda não alocado entre as duas:**

| Item | Preço unit. (loja) | Observação |
|---|---|---|
| Serviço de zincagem | R$2,20/kg (4,74kg cotados) | R$10,43 — galvanização das barras cortadas sob medida (Estação-01 + Estação-03) |
| Ferro laminado cantoneira 3/4"×1/8" (CA3418) | R$42,28/un (barra) | Uso não especificado na lista original — confirmar destino |
| **Subtotal Compartilhado (zincagem + cantoneira)** | | **R$52,71** (10,43 + 42,28) |

**Estação-02** (post de fixação do pluviômetro de báscula PB10 — apenas 2m de tubo de ferro galvanizado 1½", sem T/joelho):

| Item | Preço unit. (loja) | Observação |
|---|---|---|
| Tubo de ferro galvanizado 1½" (barra 6m R$132,04) | R$22,007/m | 2m necessários → R$44,01 |
| Barra chata Fe galvanizado 1/2"×1/8" (mesmo preço já usado, barra 6m R$16,07) | R$2,678/m | 3m necessários → R$8,04 |
| Parafuso para Madeira Phillips Chata 3.0×30 Aço Carbono Bicromatizado | R$0,12/un | 8 unidades → R$0,96 |
| **Subtotal (tubo + barra + parafusos)** | | **R$53,01** (44,01 + 8,04 + 0,96) |

> **Estação-01 e Estação-03**: como as barras de tubo de ferro galvanizado 3/4" são sempre vendidas em comprimento fixo de 6m, optou-se por custear pelo metro/cm efetivamente necessário ao projeto (Estação-01: 7m × R$24,695/m = R$172,87; Estação-03: 3m × R$24,695/m = R$74,09), em vez de tentar prever quantas barras inteiras a loja vai vender.
>
> **Já precificado nesta rodada** (2026-07-07/09, loja física/local, preço por metro a partir de barras de 6m): barra Fe galvanizado 1½"×3/16" (R$77,09/barra), barra Fe galvanizado 3/4"×3/16" (R$48,39/barra), barra chata Fe galvanizado 1/2"×1/8" (R$16,07/barra), tubo de ferro galvanizado 1½" (R$132,04/barra) — ver linhas nas tabelas de Estação-01/02/03 acima e na seção de calibração abaixo. Fonte de alimentação 12V 2A bivolt (Estação-01, retrofit) também precificada — Mercado Livre, kit 2un R$22,99, frete grátis. O cabo de energia 1,5mm² par 5m **não é contabilizado** (fios/cabos soltos fora do escopo, por decisão do autor).

### Equipamentos de Calibração de Campo

**Não entram no custo de nenhuma estação** — são instrumentos de referência/aferição, não hardware instalado:

| Item | Fornecedor | Preço unit. | Qtd | Subtotal |
|---|---|---|---|---|
| Régua limnimétrica — adesivo vinil para piso 20×200cm (61,85, rende 4 réguas)¹ | Gráfica local | R$15,46/régua | 1 | R$15,46 |
| Pluviômetro de copo 150mm Incoterm | Mercado Livre | R$33,19 | 1 | R$33,19 |
| Viga de alumínio 5×10cm×3m (TG072P Tubo retangular 101,60×50,80×1,4mm pesado, estrutura da régua) | Loja física/local (barra 6m R$422,09) | R$70,348/m | 3m | R$211,05 |
| Barra Fe galvanizado 3/4"×3/16" — corte 3×30cm (estrutura da régua) | Loja física/local (barra 6m R$48,39) | R$8,065/m | 90cm | R$7,26 |
| Bucha Plástica 8.0×40.0 (fixação da régua) | Loja física/local | R$0,11/un | 6 | R$0,66 |
| Parafuso Soberba Sextavada 8×30 Inox 304/A2 Passivado (fixação da régua) | Loja física/local | R$1,37/un | 6 | R$8,22 |
| Suporte do Pluviômetro de copo — Parafuso Madeira Phillips Chata 4.5×45 Aço Carbono Bicromatizado | Loja física/local | R$0,34/un | 4 | R$1,36 |
| **Subtotal** | | | | **R$277,20** |

¹ Corrigido: o adesivo rende **4 réguas**, não 2 como calculado antes (61,85/4 = R$15,46/régua, não R$30,93).

> Estrutura da régua (Estação-03) — viga de alumínio, barra 3/4"×3/16" e parafusos/bucha de fixação já precificados na tabela acima.

### Itens de infraestrutura geral

Compartilhados entre estações, não ligados a um Ref. específico nem a uma estação só:

| Item | Uso | Fornecedor | Preço unit. | Qtd | Subtotal |
|---|---|---|---|---|---|
| Abraçadeira HellermannTyton T30R 150×3,6mm (pacote 500un) | Ferragens de fixação (Estação-02/03) | Mercado Livre | R$158,50/pacote (≈R$0,317/un) | 1 pacote | R$158,50 |
| Cabo Manga 4 vias 4×26 AWG blindado (rolo 20m) | Cabos/conectores externos (Estação-02/03/Gateway) | Mercado Livre | R$76,50/rolo (≈R$3,825/m) | 1 rolo | R$76,50 |

**Baterias candidatas ainda sem estação definida:**

| Item | Preço | Observação |
|---|---|---|
| Bateria Selada 12V Moura VRLA \| Luz de Emergência 12V 3,5Ah | R$148,00 (já com imposto+frete, Mercado Livre) | Não usada em Estação-02 nem Estação-03 nesta rodada — candidata a Gateway ou reserva |

---

## Resumo de Custos

| Estação | Eletrônica + sensores (Tabelas 1+2 + itens manuais, sem ferragem) | Ferragem/estrutura |
|---|---|---|
| **Estação-02** (pluviométrica) | **R$2.030,94** | R$53,01 (tubo de ferro galvanizado 1½" + barra chata + parafuso madeira, ver tabela) — sem T/joelho, item descartado |
| **Estação-03** (cota de nível) | **R$1.483,55** | Parcial: R$98,31 (cotovelo + tubo de ferro galvanizado 3/4" + barra 1½" + barra chata, ver tabela) + parte da zincagem/cantoneira compartilhados; régua (calibração, fora do custo da estação) já tem viga+barra 3/4"+parafusos precificados |
| **Estação-01** (retrofit estrutural) | Não se aplica isoladamente — reaproveitaria os R$1.483,55 da Estação-03 se a substituição avançar | R$242,12 (2×T + tubo + fonte 12V + barras 1½"/3/4", ver tabela) + parte da zincagem/cantoneira compartilhados |
| **Gateway** | **R$599,51** | Não se aplica (indoor, case impresso, sem post) |

Valores acima **excluem** equipamento de calibração de campo (régua, pluviômetro de copo) e infraestrutura genérica compartilhada (abraçadeira, cabo manga) — ver seções próprias.

---

## Nota sobre Frete

Regra geral: frete excluído do preço unitário/subtotal de cada linha, porque dilui quando os itens são comprados no mesmo pedido — somar o frete "cheio" de cada anúncio individualmente infla o custo e não é citável de forma justa.

**Exceções aplicadas nesta rodada** (compras avulsas onde o frete não dilui contra outros itens, ou onde foi explicitamente pedido para contabilizar):
- **NUCLEO-F103RB**: frete somado ao preço + imposto (compra isolada de um único item); valor ajustado pelo autor para R$189,11 em 2026-07-07.
- **Nucleo L476RG**: idem, ajustado pelo autor para R$245,78 (frete incluso) em 2026-07-07.
- **LilyGo T-SIM7000G**: idem, ajustado pelo autor para R$395,51 (imposto+frete) em 2026-07-07.
- **Chave DPDT push (SW4)**: valor fornecido já veio como "(preço + frete)/100", sem imposto separado — usado literalmente como dado.
- **Pluviômetro de báscula PB10**: frete de R$40,90 somado (compra isolada de item de alto valor no Mercado Livre).
- **Abrigo meteorológico TPH**: frete de R$41,28 somado (compra isolada de item único).
- Todos os itens do Mercado Livre listados como "candidatos"/"infraestrutura geral"/painel solar/baterias já vêm com imposto e frete embutidos no preço exibido pelo próprio anúncio (compra individual, não há o que diluir).

Uma estimativa de frete agregado para o restante das compras AliExpress (por fornecedor, assumindo pedidos consolidados) será calculada quando a lista estiver mais completa.

---

Itens já resolvidos/descartados, sem ação necessária:
- Conectores M12 (5 variantes, Widsey Store): GX12 foi o conector escolhido — M12 não é mais necessário.
- Soquete fêmea 2,54mm 1×40 vias ((7,45+1,91)/5 = R$1,87/tira): preço já levantado, sem Ref. específico atribuído — usar se algum conector exigir pino fêmea.
- Módulo FRAM MB85RC256V e EEPROM AT24C256 (WAVGAT): pertencem ao bench `station-fram-test` / Issue #159, fora do escopo desta issue.
- Ferro laminado cantoneira 3/4"×1/8" (Zinca Rápido, R$42,28/barra): uso não alocado entre estações — descartado do levantamento final.
- Parafusos M4×40 do abrigo térmico (Estação-02/03): não precificados — fora do escopo final desta issue.
