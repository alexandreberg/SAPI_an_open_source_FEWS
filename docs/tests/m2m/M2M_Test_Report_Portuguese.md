# Testes dos cartões SIM — M2M

**Data:** 03/03/2026  
**Autor:** Alexandre Nuernberg  
**GitHub Issue:** #37  
**Sketch path:** `AppTest/gateways/gateway_M2M_test-01/` (sketch de teste, mantido no repositório de desenvolvimento privado)  

---

## 1. Propósito

Validar a conectividade celular NB-IoT no hardware LilyGO T-SIM7000G
usando diferentes cartões SIM e bandas de frequência, confirmando que os dados podem ser
transmitidos do campo para o servidor SAPI de produção sem Wi-Fi.

Cinco cartões SIM estão disponíveis para teste, abrangendo duas operadoras e dois
provedores de APN. Para cada SIM, todas as bandas de frequência suportadas serão testadas
sempre que possível (Banda 28, Banda 3, Banda 8 — consulte a Seção 4).

---

## 2. Hardware de Teste

| Parâmetro         | Valor                                      |
|-------------------|--------------------------------------------|
| Placa             | LilyGO T-SIM7000G V1.1                     |
| MCU               | ESP32-D0WD-V3 rev3.1, 240 MHz, 4 MB Flash |
| PSRAM             | Enabled (`-DBOARD_HAS_PSRAM`)              |
| Modem             | SIMCOM SIM7000G firmware R1529             |
| USB-Serial port   | `/dev/ttyACM0`, 115200 baud                |
| Upload speed      | 921600 baud                                |

### 2.2 Status dos LEDs

| LED                             | Satatus                       | Significado                         |
|---------------------------------|---------------------------------|---------------------------------|
| ESP32 onboard (GPIO 12)         | OFF (normal)                    | Running, no event               |
| ESP32 onboard (GPIO 12)         | Brief ON (~200 ms)              | HTTP 200 received successfully  |
| SIM7000G **STATUS** (red solid) | ON                              | Modem powered on                |
| SIM7000G **NETLIGHT** (red)     | Fast blink (~300 ms period)     | Searching for network           |
| SIM7000G **NETLIGHT** (red)     | Slow blink (1 s ON / 3 s OFF)  | Registered, data session active |
| SIM7000G **NETLIGHT** (red)     | OFF                             | Modem off or deep sleep         |

---

## 3. Software

### 3.3 Comandos AT para a configuração do modem

Aplicado dentro de um ciclo `CFUN=0 → configurações → CFUN=1` em cada inicialização
(consulte a Seção 5.2 para saber por que o ciclo CFUN é obrigatório):

| AT Command                  | Propósito                                              |
|-----------------------------|------------------------------------------------------|
| `AT+CFUN=0`                 | Desativar rádio — limpa qualquer estado CGATT travado.         |
| `AT+CNMP=38`                | Somente LTE (sem fallback para 2G/3G)                         |
| `AT+CMNB=2`                 | NB-IoT (`2` = NB-IoT, `1` = LTE-M/CAT-M1, `3` = automático) |
| `AT+CBANDCFG="NB-IOT",28`  | Banda 28 (700 MHz) — variação por teste, consulte a tabela abaixo. |
| `AT+CFUN=1`                 | Reative o rádio com as novas configurações.                    |

**Configuração da Banda para cada teste NB-IoT:**

| Banda           | `AT+CMNB` | `AT+CBANDCFG`  |
|------------------|-----------|----------------|
| NB-IoT — Band 28 | `2`       | `"NB-IOT",28`  |
| NB-IoT — Band 3  | `2`       | `"NB-IOT",3`   |
| NB-IoT — Band 8  | `2`       | `"NB-IOT",8`   |

> Todos os cartões SIM neste teste (A, B, C, D) estão provisionados apenas para **NB-IoT**.
> Eles não serão registrados em LTE-M ou LTE padrão. Consulte a Seção 8 para a
> diferença entre NB-IoT, LTE-M e LTE.

### 3.4 Referência do status de registro CEREG/CREG

`AT+CEREG?` é o comando principal para registro LTE/NB-IoT. O modem responde com `+CEREG: <n>,<stat>`, onde `stat` é o estado do registro:

| `stat` | Nome | Significado para NB-IoT | O que faz |
|--------|------|--------------------|------------|
| `0` | Não registrado, não está procurando | O modem desistiu da busca — o rádio pode estar desligado, o SIM não inserido ou `AT+CGATT=0` foi chamado | Forçar o ciclo `CFUN=0` → `CFUN=1` para reiniciar o rádio |
| `1` | **Registrado — rede doméstica** | ✅ SIM vinculado à célula da própria operadora | Prossiga com `gprsConnect()` |
| `2` | Buscando | O modem está ativamente procurando uma célula na banda configurada | Aguarde — normal durante o procedimento de conexão |
| `3` | **Registro negado** | O modem encontrou uma célula e enviou uma solicitação de conexão, mas a **rede rejeitou o SIM** | Verifique o provisionamento: banda incorreta (roaming não permitido), SIM não ativado para NB-IoT ou IMEI não listado. |
| `4` | Desconhecido | Estado transitório/incerto | Aguarde alguns instantes e repita a consulta |
| `5` | **Registrado — roaming** | ✅ SIM conectado a uma célula de operadora estrangeira | Prossiga com `gprsConnect()` |
| `ERROR` | Comando não suportado | `AT+CEREG` é específico para LTE/EPS — retornado quando o subsistema EPS do modem **não está inicializado**, geralmente porque o SIM não possui provisionamento LTE (SIM somente 2G/GPRS) | Confirme o tipo de SIM com a operadora; teste com `AT+CNMP=2` (automático) + `AT+CREG?` para verificar o registro 2G |

> **`stat=3` vs `stat=2` — principal diferença de diagnóstico:**
> - `stat=2` sempre → nenhuma célula encontrada nesta banda (sem cobertura ou banda incorreta)
> - `stat=3` → célula encontrada, tentativa de conexão, **a rede rejeitou o SIM**
>
> Obter `stat=3` significa que a banda e a cobertura estão corretas — o problema está nas permissões de provisionamento ou roaming do SIM nessa operadora/célula específica.

`AT+CREG?` funciona da mesma forma, mas para registro comutado por circuito **2G/3G** —
ele nunca atinge `stat=1` no modo somente LTE (`AT+CNMP=38`) e é exibido nos logs
apenas como um diagnóstico secundário.

### 3.5 Modo de Depuração de Comandos AT

Descomente para despejar todas as trocas AT em Serial:

```cpp
#define DUMP_AT_COMMANDS
```

Capturar o log serial para arquivo (Linux):
```bash
stty -F /dev/ttyACM0 115200 raw -echo && cat /dev/ttyACM0 | tee /var/tmp/gateway-M2M.log
```

---

## 4. SIM Cards

| # | Cor | CCID (final) | Proprietário  | Operador        | Provedor APN | APN                    | User / Pass         | Notas                             |
|---|-------|--------------|--------|-----------------|--------------|------------------------|---------------------|-----------------------------------|
| A | 🟡 Yellow | <ICCID> | Job    | TIM Brasil      | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (no 2G/3G/LTE-M)     |
| B | 🔴 Red    | …00859     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (same provisioning as A) |
| C | 🟢 Green  | …64104     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (same provisioning as A) |
| D | 🩵 Cyan   | …529146    | Personal | Vivo (consumer M2M) | Vivo M2M | `smart.m2m.vivo.com.br` | (none)           | **Confirmed LTE-M only** (Kite Platform: `LTE/LTE-M ativo ✅`, NB-IoT not provisioned). Data roaming **disabled** — SIM denied on TIM towers. See §5.8. |
| E | 🩷 Pink   | …68771     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | `AT+CEREG` returns ERROR — **hypothesis: 2G/GPRS-only SIM, no LTE provisioning** |

---

## 5. Resultados dos Testes

### 5.1 Tabela de Resultados

Uma linha por combinação (SIM × banda).

**Payload** = Estrutura `SensorData` serializada em MessagePack (15 campos).

| # | SIM | Cor | Operador | Rede | Banda | APN | CCID | IMEI | CSQ | Payload | Resultado |
|---|-----|-------|----------|---------|------|-----|------|------|-----|---------|--------|
| 1 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | <ICCID> | <IMEI> | 18 (Good) | 212 B | ✅ HTTP 200 |
| 2 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | <ICCID> | <IMEI> | 13 (Good) | 212 B | ✅ HTTP 200 |
| 3 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | <ICCID> | <IMEI> | — | — | ⏳ |
| 4 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 5 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 6 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | — | — | — | — | ⏳ |
| 7 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 8 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=2 timeout (§5.4) |
| 9 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | — | — | — | — | ⏳ |
| 10 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 28 — 700 MHz | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ❌ CEREG=3 (§5.3, §5.4) |
| 11 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 3 — 1800 MHz | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ❌ CEREG=ERROR ⚠️ (§5.5, §5.7) |
| 12 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 8 — 900 MHz  | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ⏳ |
| 13 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br`   | — | — | — | — | ❌ CEREG=ERROR (§5.5) |
| 14 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br`   | — | — | — | — | ❌ CEREG=ERROR (§5.5) |
| 15 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br`   | — | — | — | — | ⏳ |

> **Nota sobre a escala CSQ:** O CSQ (retornado por `AT+CSQ`) varia de 0 a 31, mais 99 para desconhecido.
> Ele é mapeado para RSSI por meio de: `RSSI (dBm) = (CSQ × 2) − 113`. Categorias padrão da indústria:
>
> | CSQ   | RSSI (dBm)        | Category   |
> |-------|-------------------|------------|
> | 0–9   | ≤ −95 dBm         | Marginal   |
> | 10–14 | −93 to −85 dBm    | OK         |
> | 15–19 | −83 to −75 dBm    | Good       |
> | 20–24 | −73 to −65 dBm    | Very Good  |
> | 25–31 | −63 dBm or better | Excellent  |
> | 99    | —                 | Unknown    |
>
> Para NB-IoT, a tecnologia foi projetada especificamente para funcionar com níveis de sinal baixos
> (até −120 dBm RSRP / ~CSQ 5). Um CSQ de 10 a 18 é típico e totalmente adequado para uplinks NB-IoT.


### Lista dos MNCs das operadoras

| MCC   | MNC  | Operadora               |
| ----- | ---- | ----------------------- |
| 724   | 00   | Telemig / legado        |
| 724   | 01   | Vivo (legado)           |
| **724 | 02** | TIM                     |
| **724 | 03** | Claro                   |
| **724 | 04** | Vivo                    |
| **724 | 05** | Claro                   |
| **724 | 06** | Vivo                    |
| 724   | 07   | CTBC / Algar            |
| **724 | 08** | TIM                     |
| 724   | 10   | Vivo                    |
| 724   | 11   | Vivo                    |
| **724 | 16** | TIM                     |
| 724   | 23   | Vivo                    |
| **724 | 31** | Oi (legado)             |
| 724   | 34   | Algar                   |
| 724   | 54   | Conecta / MVNO          |
| 724   | 99   | testes / redes privadas |



### 5.2 Detalhes do Teste Bem-Sucedido — SIM A, TIM, Banda 28 do NB-IoT (03/03/2026)

**Log file:** `M2M_TIM_datatem.txt`

#### AT+CPSI? Output

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508013,260,EUTRAN-BAND28,9362,0,0,-3,-89,-87,19
```

> **O que é AT+CPSI?**
Este é um comando específico do SIM7000 que consulta as informações da célula servidora atual do modem. **Todos os valores vêm de medições recebidas via rádio da torre celular** — eles representam as condições reais de rádio que o modem detectou, não o que foi configurado no software. O modem mede continuamente esses valores a partir dos sinais de referência da estação base.

| Field | Value | Meaning |
|-------|-------|---------|
| System Mode | `LTE NB-IOT` | Technology actually connected. Confirms NB-IoT (not LTE-M or GSM). |
| Operation Mode | `Online` | Active data session (PDP context open and IP assigned). |
| MCC-MNC | `724-04` | Mobile Country Code 724 = Brazil; MNC 04 = TIM Brasil. Identifies the operator the modem registered with. |
| TAC | `0xAF3C` (= 44860) | Tracking Area Code — a network-assigned ID for a group of cells used for paging. The value comes from the network; it has no fixed geographic meaning visible to us. |
| Serving Cell ID | `75508013` | E-UTRAN Cell Global ID. The unique identifier of the specific cell tower the modem is connected to. |
| Physical Cell ID | `260` | PCellID (0–503). A local radio identifier used by the modem for cell synchronisation and reselection. Not globally unique. |
| Freq Band | `EUTRAN-BAND28` | Band 28 = 700 MHz (as configured with `AT+CBANDCFG`). Confirms the modem found and connected to a tower on the requested band. |
| EARFCN | `9362` | E-UTRA Absolute Radio Frequency Channel Number. In Band 28, EARFCN 9362 → DL frequency ≈ 773.2 MHz. This is the exact carrier frequency of the cell. |
| DL BW / UL BW | `0` / `0` | Downlink / Uplink bandwidth. In NB-IoT, `0` = 200 kHz narrowband channel (normal for NB-IoT). |
| RSRQ | `−3 dB` | Reference Signal Received Quality. Ratio of signal to total received power (range −34 to 0 dB). **−3 dB is very good** — means the reference signals are strong relative to interference. |
| RSRP | `−89 dBm` | Reference Signal Received Power. Actual power of the tower's reference signals at the modem (range −140 to −44 dBm). **−89 dBm is moderate — typical urban NB-IoT.** Coverage threshold for NB-IoT is around −115 dBm. |
| RSSI | `−87 dBm` | Total Received Signal Strength — includes all signals and noise. Should be close to RSRP for a clean band. |
| RSSNR | `19 dB` | Reference Signal Signal-to-Noise Ratio. **19 dB is good.** > 10 dB is generally sufficient for reliable data. |

#### Resuktado HTTP

```
POST http://ilha3d.com/sapi/sensorData/receive-data.php
HTTP 200 OK
{"success":true,"message":"Data received and stored successfully","station_id":99}
```

Confirmado na tabela `measurements` com todos os 15 campos sentinela corretos:
`level_cm=888`, `temperature_C=100`, `pressure=999`, `s_gsm=<real CSQ>`, etc.

### 5.3 Teste Falhou — SIM D 🩵 Cyan, Vivo Personal, Banda 28 (2026-03-03)

**Log file:** `M2M_VIVO_ilha3d.txt`

`CEREG stat=3` = registro negado. O modem procurou (stat=2) por ~84 s,
encontrou uma célula e, em seguida, teve a solicitação negada. O padrão é consistente com a Seção 5.4 (rejeição de roaming na
Banda 28 da TIM). Além disso, o SIM D pode estar provisionado para **LTE-M** em vez de NB-IoT
— isso explicaria o CEREG=3 persistente mesmo nas Bandas 3/8 (a ser confirmado em um
teste LTE-M separado com `AT+CMNB=1`).

**Próximo passo:** Teste o SIM D com `AT+CMNB=1` (modo LTE-M) após a conclusão da varredura de banda NB-IoT
para os SIMs B e C.

### 5.4 Testes com Falha — SIM B e C (Vivo Datatem), Banda 28 (04/03/2026)

**Log files:** `M2M_VIVO_00859_datatem.txt` (SIM B) · `M2M_VIVO_64104_datatem.txt` (SIM C)

Ambos os SIMs seguiram o mesmo padrão:

1. Após CFUN=1, o modem inicia a busca: `CEREG: 0,2`
2. Cerca de 60 a 84 segundos depois, transita para `CEREG: 0,3` (registro **negado**)
3. Permanece em stat=3 até o tempo limite de 180 segundos → o ESP32 reinicia → mesmo resultado na nova tentativa

#### Por que stat=3 e não stat=2 (busca travada)?

`CEREG stat=3` significa que o modem **encontrou** uma célula NB-IoT na Banda 28 e enviou uma
solicitação de conexão — mas a **rede a rejeitou**. Se não houvesse cobertura, o modem
permaneceria em stat=2 (ainda buscando) indefinidamente.

Hipótese da causa raiz: rejeição de roaming na infraestrutura da TIM

A célula NB-IoT da Banda 28 na área pertence à **TIM** (confirmado pelo SIM A sucedendo
com MCC-MNC `724-04` = TIM Brasil). Os SIMs NB-IoT da Vivo (B e C) não têm permissão para
roaming na infraestrutura NB-IoT da TIM — os acordos de roaming NB-IoT no Brasil são
limitados e frequentemente não habilitados entre as operadoras.

A Vivo pode implantar NB-IoT em uma **banda diferente** na área de Florianópolis. As bandas de implantação NB-IoT conhecidas da Vivo no Brasil incluem a Banda 3 (1800 MHz) e a Banda 8 (900 MHz).

#### Próximos passos

Testar os SIMs B e C nas bandas 3 e 8 com o mesmo sketch de firmware
(`#define NBIOT_BAND` alterado de acordo). Se a Vivo tiver uma célula NB-IoT em uma dessas
bandas na área, o CEREG deverá atingir stat=1 (home) em vez de stat=3.

### 5.6 Detalhes do teste bem-sucedido — SIM A 🟡 Amarelo, TIM, Banda NB-IoT 3 (04/03/2026)

**Log file:** `M2M_TIM_Band-3_yellow.txt`

#### AT+CPSI? Output

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508009,17,EUTRAN-BAND3,1352,0,0,-3,-88,-87,18
```

| Field | Value | Meaning |
|-------|-------|---------|
| System Mode | `LTE NB-IOT` | NB-IoT confirmed |
| MCC-MNC | `724-04` | TIM Brasil |
| TAC | `0xAF3C` (44860) | Same tracking area as Band 28 — same tower cluster |
| Serving Cell ID | `75508009` | Different cell from Band 28 (75508013) — Band 3 carrier on same tower |
| Freq Band | `EUTRAN-BAND3` | 1800 MHz confirmed |
| EARFCN | `1352` | DL ≈ 1835.2 MHz (Band 3) |
| RSRQ | `−3 dB` | Very good |
| RSRP | `−88 dBm` | Equivalent to Band 28 (−89 dBm) |
| RSSNR | `18 dB` | Good |

Todas as 3 transmissões retornaram HTTP 200. A CSQ caiu 13 → 6 → 3 durante o teste (desvanecimento do sinal), mas a capacidade de penetração profunda do NB-IoT manteve a conexão viável.

**O TIM está confirmado como funcionando nas Bandas 28 e 3.**

---
### 5.5 Teste Falhou — SIM E 🩷 Rosa, Vivo (trabalho), Banda 28 + Banda 3 (04/03/2026)

**Log file:** `M2M_VIVO_8771.txt`

Este SIM apresenta um **padrão de falha completamente diferente** dos SIMs B, C e D:

| Register | Response | Meaning |
|----------|----------|---------|
| `AT+CREG?` | `+CREG: 0,0` | Not registered, not searching (2G/3G) |
| `AT+CEREG?` | `ERROR` | Command not recognised in current modem state |

O modem nunca entra em estado de busca (`stat=2`) — `CREG` permanece em `0,0`
durante todos os 180 segundos. Mais importante, `AT+CEREG` retorna `ERROR` (e não
`+CEREG: 0,x`) em todas as verificações.

#### Por que `AT+CEREG` está retornando ERROR?

`AT+CEREG` é um comando específico para LTE/EPS. No SIM7000G, ele retorna ERROR quando
o subsistema EPS (Evolved Packet System) do modem não está inicializado — o que acontece
quando o SIM não possui provisionamento LTE. O modem não consegue configurar um contexto EPS para um
SIM não-LTE, então o próprio comando falha.

Compare com os SIMs B e C: esses retornaram `+CEREG: 0,2` (o modem está procurando por células LTE), o que significa que seu subsistema EPS **foi** inicializado — apenas a conexão foi
posteriormente negada.

Hipótese da causa raiz: SIM somente 2G/GPRS

O SIM E provavelmente está configurado para **somente 2G GPRS** — não para NB-IoT ou LTE-M. Com `AT+CNMP=38` (modo somente LTE), o modem bloqueia a busca por redes 2G, resultando em:

1. O modem nunca busca redes 2G → `CREG: 0,0` (sem busca)
2. O portador EPS nunca é inicializado → `AT+CEREG` retorna ERRO
3. Tempo limite de 180 s → reinicialização → mesmo resultado

Próximo passo

- Confirme com a operadora se este SIM está configurado para LTE (NB-IoT ou LTE-M)
- Diagnóstico rápido: altere `AT+CNMP=38` → `AT+CNMP=2` (2G/3G/LTE automático) e

verifique se `AT+CREG?` atinge stat=1. Se o dispositivo se registrar na rede 2G, o SIM é somente GPRS.
- Resultado da Banda 3 (04/03/2026): CEREG=ERRO confirmado — igual à Banda 28 (ver linha 14)

### 5.7 Anomalia — SIM D 🩵 Ciano, Banda 3 mostra CEREG=ERROR (04/03/2026)

**Arquivo de log:** `M2M_VIVO_Band-3_ilha3d_cian.txt`

O teste original da Banda 28 (`M2M_VIVO_ilha3d.txt`, 03/03/2026) mostrou `CEREG: 0,3`
(registro negado — o SIM encontrou uma célula e foi rejeitado). No entanto, o log do teste da Banda 3
mostra `CEREG=ERROR` — o mesmo padrão do SIM E 🩷 Rosa (SIM somente 2G).

O log também captura uma inicialização da Banda 28 (firmware antigo) antes da execução da Banda 3, e ambas
mostram `CEREG=ERROR` durante todo o processo.

**Possíveis explicações:**

1. **Chip incorreto inserido:** O chip ciano foi trocado acidentalmente pelo chip rosa
ao trocar os SIMs — o registro foi rotulado como ciano, mas na verdade se refere ao comportamento do chip rosa.

Esta é a explicação mais provável, visto que o primeiro teste mostrou claramente CEREG=3.

2. **Estado de inicialização diferente:** É improvável que o status mude de 3 para ERRO.

**Ação:** Verifique fisicamente qual chip está na placa ao executar este teste e
execute-o novamente com o SIM ciano confirmado no lugar.

### Teste LTE-M 5.8 — SIM D 🩵 Ciano, Banda 28, Ambiente Interno (04/03/2026)

**Arquivo de log:** `M2M_VIVO_LTE-M_B28_ilha3d_cian.txt`

**Resultado:** ❌ CEREG=3 durante todo o teste — registro negado imediatamente (stat=3 desde a
primeira consulta em 2 s). Dois ciclos completos de 180 s foram capturados antes que o log fosse interrompido.

#### Análise da Plataforma Kite (portal Vivo M2M)

O SIM foi inspecionado em [kiteplatform-vivo-br.telefonica.com](https://kiteplatform-vivo-br.telefonica.com/).

Principais conclusões:

| Parameter | Value | Implication |
|-----------|-------|-------------|
| SIM Status | **Ativo** | SIM is active — not suspended |
| LTE/LTE-M ativo | ✅ ON | LTE-M technology is correctly provisioned |
| NB-IoT | not listed | **NB-IoT is NOT in this plan** — explains all NB-IoT CEREG=3/ERROR results |
| 2G ativo | ❌ OFF | No 2G fallback |
| 3G ativo | ❌ OFF | No 3G fallback |
| Tráfego de dados — Local | ✅ ON | Data on Vivo's own network: enabled |
| **Tráfego de dados — Em roaming** | ❌ **OFF** | **Data on other operators' networks: DISABLED** ← root cause |
| Serviço de VPN | ✅ ON | APN `smart.m2m.vivo.com.br` routes through private VPN |
| Tecnologias Usadas (LTE-M) | ❌ never used | Confirms no successful LTE-M session has ever occurred |
| Last connection event | 03-03-2026 — "SIM não registrado no GSM" | No successful registration since provisioning |

#### Causa raiz

A área (Cachoeira do Bom Jesus, Florianópolis) possui **células LTE-M da TIM na Banda 28**
(confirmado por testes NB-IoT do SIM A no MCC-MNC `724-04` = TIM). A infraestrutura LTE-M da Vivo
pode não estar presente neste local. Com o **roaming de dados desativado**,
o SIM da Vivo encontra a célula da TIM imediatamente, mas a rede rejeita a conexão —
daí o CEREG=3 instantâneo.

Este **não é um problema de firmware ou hardware**. A solução requer a ativação do roaming de dados nacional no SIM.

#### Por que a opção não está visível na Plataforma Kite

A operação "Ativar roaming de tráfego de dados" (manual da Plataforma Kite, pág. 125) requer
**perfil de usuário Administrador ou Demo Kit**. A conta atual é um perfil padrão de cliente final
e a opção aparece como somente leitura. Para ativar o roaming:

- Entre em contato com o suporte Vivo M2M e solicite: *"Ativar tráfego de dados em roaming nacional 
sem ICC <ICCID>"*
- Ou: teste em um local com **cobertura Vivo LTE-M** confirmada (sem necessidade de roaming)

#### Teste de localização externa — concluído (04/03/2026)

**Arquivo de log:** `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt` — consulte a seção 10.3 para análise completa.

---

## 6. Problemas conhecidos e soluções alternativas

### 6.1 TINY_GSM_MODEM_SIM7000SSL falha no NB-IoT

A variante SSL do TinyGSM usa `AT+CNACT=1` para ativação GPRS e aguarda a
resposta não solicitada `+APP PDP: ACTIVE`. No SIM7000G em modo NB-IoT (`AT+CMNB=2`),
este comando não é compatível e a ativação sempre falha.

**Solução alternativa:** Use `#define TINY_GSM_MODEM_SIM7000` (TCP simples) com `TinyGsmClient`.
O HTTP (porta 80) é usado em vez do HTTPS. O caminho `AT+SAPBR`/`AT+CGACT` da variante simples funciona corretamente no NB-IoT.

**Futuro caminho HTTPS:** Envolva `TinyGsmClient` com
[OPEnSLab-OSU/SSLClient](https://github.com/OPEnSLab-OSU/SSLClient) para lidar com TLS
no lado do ESP32 via BearSSL, ignorando completamente a pilha SSL do modem.


### 6.2 AT+CGATT=0 Interrompe o Registro NB-IoT

No NB-IoT, `AT+CGATT=0` (emitido internamente pela função `gprsDisconnect()` do TinyGSM) interrompe completamente o registro EPS.
O modem então reporta `CEREG: 0,0` (não está buscando — o rádio aparece
desligado) na próxima inicialização e nunca se recupera sozinho.

**Causa raiz:** No NB-IoT, a conexão EPS e a conexão PDN são acopladas; desativar o
GPRS com CGATT=0 também impede que o rádio faça buscas.

**Solução alternativa:** Force um ciclo `CFUN=0` → aplicar configurações → `CFUN=1` em `initModem()` a cada inicialização.
Isso reinicia o rádio corretamente, independentemente do estado da sessão anterior.

### 6.3 Pulso PWRKEY Deve Ter Duração ≥ 1,5 s

A folha de dados do SIM7000G exige que o sinal PWRKEY seja ativado por ≥ 1 s para acionar a inicialização.
A placa LilyGO utiliza um transistor que inverte a lógica (GPIO 4 ALTO = PWRKEY BAIXO = ativo).

Um pulso de 300 ms é insuficiente — o módulo não responde.

### 6.4 SIM Vivo M2M — Registro Negado (CEREG stat=3)

O SIM pessoal Vivo M2M (SIM D) retornou `CEREG stat=3` (negado). Isso não é um problema de firmware — requer investigação através do portal do operador Vivo M2M (consulte §5.3).

---

## 7. Passos para Reproduzir

1. **Grave o sketch:** `AppTest/gateways/gateway_M2M_test-01/` (sketch de teste, mantido no repositório de desenvolvimento privado)

``bash

cd AppTest/gateways/gateway_M2M_test-01/

cp include/credentials_sample.h include/credentials.h

* preencha a chave da API em credentials.h

~/.platformio/penv/bin/pio run -t upload
```
2. **Configure o APN e a banda** em `src/main.cpp` antes de gravar (consulte a Seção 3.3).

3. **Monitore a porta serial:**

``bash

minicom -D /dev/ttyACM0 -b 115200 | tee /var/tmp/gateway-M2M.log

```
> Mate o minicom antes de atualizar: `pkill -f "minicom.*ttyACM0"`

4. **Sequência de inicialização esperada:**

- `[MODEM] Desativando o rádio...` ​​→ `[MODEM] Reativando o rádio...`

- `[NET] AT+CEREG? → +CEREG: 0,2` (buscando)

- `[NET] LTE/EPS registrado via CEREG ✓`

- `[NET] GPRS conectado | IP local: ...`

- `[HTTP] Status: 200`

5. **Verificar no banco de dados:**

   ```sql
   SELECT * FROM measurements WHERE id_station = 99 ORDER BY id DESC LIMIT 5;
   ```

---

---

## 8. Terminologia: NB-IoT, LTE-M e LTE

Esses três nomes estão relacionados, mas se referem a tecnologias diferentes. Todos os três pertencem à família de padrões LTE, razão pela qual compartilham faixas de frequência e infraestrutura,
mas sua velocidade, latência e uso pretendido diferem significativamente.

```
Família LTE (padrão de rádio 4G):
├── LTE banda larga (Cat-4, Cat-6, Cat-12…) ← padrão 4G em smartphones
├── LTE-M / CAT-M1 (Cat-M1) ← IoT, velocidade moderada, suporta voz/mobilidade
└── NB-IoT / Cat-NB1 / Cat-NB2 ← IoT, baixa velocidade, alta penetração, baixo consumo de energia
```

### NB-IoT ≠ LTE (broadband)

O NB-IoT é **tecnicamente baseado no padrão de rádio LTE** — é por isso que o SIM7000G
reporta `LTE NB-IoT` na saída `AT+CPSI?`. Ele reutiliza as bandas de frequência e a
infraestrutura de torres de celular do LTE. No entanto, é um serviço completamente separado do
"LTE" que seu smartphone usa:

| | Banda larga LTE | NB-IoT |
|---|---|---|
| Largura do canal | 20 MHz | 200 kHz (banda estreita) |
| Velocidade típica de downlink | 50–300 Mbps | 20–200 kbps |
| Projetado para | Smartphones, vídeo | Sensores IoT, baixo consumo de dados |
| Duração da bateria (dispositivo) | Horas | Meses a anos |
| Penetração (subsolos, etc.) | Padrão | Excelente (ganho de +20 dB em relação ao LTE) |

### LTE-M = CAT-M = CAT-M1 (todos são a mesma coisa)

Estes são três nomes para o mesmo padrão 3GPP:

| Nome | Origem |
|------|--------|
| **LTE-M** | LTE para Máquinas — o nome comercial |
| **CAT-M1** | LTE Categoria M1 — a designação técnica do 3GPP |
| **eMTC** | Comunicação Aprimorada do Tipo Máquina — o nome da especificação nos documentos de padrões |

O LTE-M situa-se entre o NB-IoT e o LTE padrão: mais rápido que o NB-IoT (~1 Mbps), suporta
voz e mobilidade de dispositivos (transferência entre células), mas consome mais energia que o NB-IoT.

### Resumo dos Parâmetros AT+CMNB

O SIM7000G seleciona a variante IoT via `AT+CMNB`:

| Valor de `AT+CMNB` | Tecnologia | Nome 3GPP |
|-----------------|------------|-----------|
| `1` | LTE-M | Cat-M1 / eMTC |
| `2` | NB-IoT | Cat-NB1 |
| `3` | Automático (o modem escolhe) | — |

Os cartões SIM da Datatem (A, B, C) são provisionados apenas para **NB-IoT** (`AT+CMNB=2`).

O SIM D (ciano, Vivo M2M pessoal) é confirmado como sendo apenas **LTE-M** (`AT+CMNB=1`) — consulte §5.8.

O SIM E (rosa) provavelmente é apenas 2G/GPRS — consulte §5.5.
---

---

## 9. NB-IoT Frequency Bands — Global Reference and Brazil Deployment

### 9.1 Todas as bandas NB-IoT definidas pelo 3GPP

O 3GPP definiu o suporte a NB-IoT em diversas bandas de frequência. A tabela abaixo lista todas as
bandas suportadas pelo **modem SIM7000G** (subconjunto relevante), com o status de implantação no Brasil para cada operadora.

| Band | Frequency | Common name | SIM7000G | TIM Brasil | Vivo Brasil | Claro Brasil | Notes |
|------|-----------|-------------|----------|------------|-------------|--------------|-------|
| **B1** | 2100 MHz | IMT | ✅ | ⚠️ Possible | ⚠️ SP metro only | ✗ | Mainly Asia/Europe; limited NB-IoT in Brazil |
| **B2** | 1900 MHz | PCS | ✅ | ✗ | ✗ | ✗ | North America only |
| **B3** | 1800 MHz | GSM-1800 | ✅ | ✅ **deployed** | ✅ **deployed** | ✅ **deployed** | ✅ **Tested — TIM works** |
| **B4** | 1700/2100 MHz | AWS | ✅ | ✗ | ✗ | ✗ | North America only |
| **B5** | 850 MHz | CLR-850 | ✅ | ✗ | LTE only | LTE only | 850 MHz used for LTE in Brazil, **not NB-IoT** |
| **B8** | 900 MHz | E-GSM | ✅ | ✗ | ✗ | ✗ | Used in Europe/Asia; **no Brazilian operator has 900 MHz NB-IoT** |
| **B12** | 700 MHz lower | US 700 lower | ✅ | ✗ | ✗ | ✗ | US-specific (AT&T) |
| **B13** | 700 MHz upper | US 700 C | ✅ | ✗ | ✗ | ✗ | US-specific (Verizon) |
| **B17** | 700 MHz | US 700 b | ✅ | ✗ | ✗ | ✗ | US-specific (AT&T) |
| **B18** | 850 MHz | Japan 850 | ✅ | ✗ | ✗ | ✗ | Japan only |
| **B19** | 850 MHz | Japan 850 ext | ✅ | ✗ | ✗ | ✗ | Japan only |
| **B20** | 800 MHz | EU 800 | ✅ | ✗ | ✗ | ✗ | Europe only (digital dividend) |
| **B26** | 850 MHz extended | CLR-850 ext | ✅ | ✗ | ✗ | ✗ | No NB-IoT deployment in Brazil |
| **B28** | 700 MHz | APT 700 | ✅ | ✅ **deployed** | ✅ **deployed** | ✅ **deployed** | ✅ **Tested — TIM works** — primary NB-IoT band in Brazil |
| **B66** | 1700/2100 MHz | AWS-3 | ✅ | ✗ | ✗ | ✗ | Americas, mainly Canada/US |

> **⚠️ = Possível, mas não confirmado.** A operadora possui LTE nesta banda, mas a implantação do NB-IoT
> não está confirmada ou está limitada às principais áreas metropolitanas (São Paulo).

### 9.2 Por que apenas as bandas 28 e 3 importam no Brasil

A regulamentação do espectro no Brasil (ANATEL) aloca frequências de forma diferente da Europa e da
América do Norte. Os pontos principais:

- **O Brasil não possui alocação de LTE/NB-IoT na banda de 900 MHz.** A banda de 900 MHz (Banda 8) é usada para
GSM legado em alguns países, mas as operadoras brasileiras usam **850 MHz (Banda 5)** para legado
e não implantaram NB-IoT nessa banda. Testar a Banda 8 em um SIM brasileiro é inútil.

- **700 MHz APT (Banda 28)** é a principal banda de banda larga/IoT no Brasil. TIM, Vivo e
Claro foram as primeiras operadoras a implantar NB-IoT aqui (2018–2019).

- **1800 MHz (Banda 3)** é a banda secundária do NB-IoT, reutilizando a infraestrutura GSM-1800.

Todas as três operadoras a possuem.

- **2100 MHz (Banda 1)** é usada para 3G/4G, mas a implantação do NB-IoT é mínima e restrita
às grandes cidades.

### 9.3 Conclusão do Teste SAPI — Varredura de Bandas NB-IoT Completa

Todas as bandas NB-IoT relevantes para o Brasil foram testadas no gateway SAPI.
Localização (Cachoeira do Bom Jesus, Florianópolis, SC):

| Band | Tested | TIM 🟡 | Vivo B 🔴 | Vivo C 🟢 | Result |
|------|--------|--------|-----------|-----------|--------|
| **Band 28** (700 MHz) | ✅ | ✅ HTTP 200 | ❌ CEREG=3 | ❌ CEREG=3 | TIM only |
| **Band 3** (1800 MHz) | ✅ | ✅ HTTP 200 | ❌ CEREG=3 | ❌ CEREG=2 | TIM only |
| **Band 8** (900 MHz) | — | — | — | — | **Not deployed in Brazil — skip** |
| **Band 1** (2100 MHz) | — | — | — | — | Not relevant for Florianópolis |

**A varredura de banda NB-IoT foi concluída. O TIM funciona em ambas as bandas implantadas. Os SIMs Vivo Datatem
são consistentemente rejeitados — trata-se de um problema de provisionamento de SIM, não de cobertura ou banda.**

---

## 10. Testes LTE-M — SIM D 🩵 Ciano (Vivo Personal M2M)

Testando todos os SIMs disponíveis para suporte a LTE-M. Espera-se que os SIMs somente NB-IoT falhem,
mas são testados para garantir a integridade do sistema.

**Firmware config for LTE-M tests:**

```cpp
#define IOT_MODE  "LTE-M"
#define IOT_CMNB  1                        // AT+CMNB=1 → LTE-M/CAT-M1
// AT+CBANDCFG="CAT-M",<band>
const char apn[] = "smart.m2m.vivo.com.br";
```

### Tabela de Resultados LTE-M 10.1

| # | SIM | Color | Band | Location | APN | Result | Log file |
|---|-----|-------|------|----------|-----|--------|----------|
| 1 | D | 🩵 Cyan | Band 28 — 700 MHz | Indoor (home) | `smart.m2m.vivo.com.br` | ❌ CEREG=3 — roaming denied (§5.8) | `M2M_VIVO_LTE-M_B28_ilha3d_cian.txt` |
| 2 | D | 🩵 Cyan | Band 28 — 700 MHz | **Outdoor** (Vivo coverage search) | `smart.m2m.vivo.com.br` | ❌ CEREG=2 timeout — no Vivo cell found (§10.3) | `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt` |
| 3 | A | 🟡 Yellow | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=2 timeout — TIM SIM is NB-IoT only; no LTE-M cell found (§11.1) | `M2M_TIM_LTE-M_B28_yellow.txt` |
| 4 | C | 🟢 Green | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3 — Vivo Datatem supports LTE-M but roaming denied on TIM cell (§11.2) | `M2M_VIVO_LTE-M_B28__green.txt` |
| 5 | E | 🩷 Pink | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3 — LTE-M provisioned, roaming denied; **not 2G-only** (§11.3) | `M2M_VIVO_LTE-M_B28_pink.txt` |
| 6 | B | 🔴 Red | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3→2 — NB-IoT+LTE-M provisioned, TIM cell denied then no Vivo cell found (§11.4) | `M2M_VIVO_LTE-M_B28_red.txt` |

### Referência de banda LTE-M 10.2 para o Brasil

| Band | Frequency | TIM LTE-M | Vivo LTE-M | Notes |
|------|-----------|-----------|------------|-------|
| **B28** | 700 MHz | ✅ deployed | ✅ deployed | Primary IoT band in Brazil |
| **B3** | 1800 MHz | ✅ deployed | ✅ deployed | Secondary; good urban coverage |

### 10.3 Análise do Teste Externo — SIM D 🩵 Ciano, Banda 28 (04/03/2026)

**Arquivo de log:** `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt`

O teste externo revelou um **padrão CEREG diferente** do teste interno:

| Phase | Indoor result | Outdoor result |
|-------|--------------|----------------|
| 0–2 s | CEREG=3 (TIM cell found, denied) | CEREG=3 (TIM cell found, denied) |
| 14 s onwards | CEREG=3 throughout | **CEREG=2** (searching, no cell found) |
| Outcome | Timeout at 180 s | Timeout at 180 s |

**Interpretação:** Em ambiente externo, o modem inicialmente encontrou a célula LTE-M da Banda 28 da TIM e
teve o acesso negado (stat=3, roaming não permitido). Após se afastar da cobertura da TIM,
ele escaneou toda a janela de 180 segundos procurando por uma **célula residencial da Vivo** e não encontrou nenhuma.

Isso confirma que **a Vivo não possui infraestrutura LTE-M da Banda 28 nesta área**.

#### Por que a Banda 3 LTE-M também não vale a pena testar

A Vivo implanta as Bandas 28 e 3 LTE-M nas **mesmas torres físicas**. Como nenhuma torre da Vivo
é visível na Banda 28, nenhuma torre da Vivo será visível na Banda 3 também.
Testar a Banda 3 produziria o mesmo tempo limite CEREG=2.

#### SIM D — Teste concluído

| Causa raiz | Inexistência de infraestrutura Vivo LTE-M na área (Cachoeira do Bom Jesus, Florianópolis) |
|---|---|
| Causa secundária | Roaming de dados desativado — não é possível usar as células LTE-M da TIM próximas |
| Opção de correção 1 | Contatar o suporte Vivo M2M: ativar o roaming de dados nacional no ICC …529146 |
| Opção de correção 2 | Implantar o gateway em uma área com cobertura Vivo LTE-M confirmada |

| **Decisão SAPI** | **O SIM D não é viável para backup celular do gateway SAPI na localização atual** |

**O SIM A 🟡 Amarelo (TIM Datatem NB-IoT) continua sendo o único SIM com funcionamento confirmado.**
Os testes continuam com o SIM A — consulte §11.
---

## 11. SIM Datatem da TIM — Validação de Produção (SIM A 🟡 Amarelo)

O SIM A já passou nos testes NB-IoT das Bandas 28 e 3 (§5.2, §5.6). Esta seção
documenta a validação adicional para uso em produção como backup celular do gateway SAPI.

### 11.1 Teste LTE-M da TIM — concluído ❌

**Arquivo de log:** `M2M_TIM_LTE-M_B28_yellow.txt`

**Resultado: CEREG=2 durante toda a varredura** — o modem escaneou por 180 s e não encontrou nenhuma célula LTE-M.

Este é um padrão distinto das falhas de roaming da Vivo (CEREG=3):

| Padrão CEREG | Significado |
|---------------|---------|
| stat=3 (SIMs Vivo) | Célula encontrada, conexão negada — problema de provisionamento/roaming |
| **stat=2 (TIM amarelo)** | **Nenhuma célula LTE-M encontrada — SIM ou rede não LTE-M** |


Duas razões combinadas:
1. **O SIM Datatem da TIM está provisionado apenas para NB-IoT** — não para LTE-M.
2. **A TIM não possui portadora LTE-M (CAT-M1) na Banda 28 nesta área** — apenas subportadoras NB-IoT.

NB-IoT e LTE-M ocupam subcanais diferentes dentro da mesma banda; a TIM implantou
NB-IoT na Banda 28 aqui, mas não LTE-M. Testar a Banda 3 LTE-M com a TIM também falharia
pelos mesmos motivos.

**SIM A — NB-IoT é o modo correto.** Teste LTE-M concluído.**

### 11.2 Teste LTE-M da Vivo Datatem (SIM C 🟢 Verde) — concluído ❌

**Arquivo de log:** `M2M_VIVO_LTE-M_B28__green.txt`

**Resultado: CEREG=3 imediatamente em 2 s** — o modem encontrou a célula LTE-M da TIM instantaneamente
e teve a conexão negada. O mesmo padrão de rejeição de roaming que a Banda 28 do NB-IoT com este SIM.

**Principal descoberta:** Ao contrário da TIM (CEREG=2 no LTE-M), o SIM verde da Vivo Datatem obtém
CEREG=3 — o que significa que seu subsistema EPS inicializa e tenta ativamente se conectar ao LTE-M.

**A Datatem fornece SIMs da Vivo para NB-IoT e LTE-M.** A falha se deve puramente
à negação de roaming na infraestrutura da TIM, e não à tecnologia do SIM.

### 11.3 Teste Vivo Datatem LTE-M (SIM E 🩷 Rosa) — concluído ❌

**Log file:** `M2M_VIVO_LTE-M_B28_pink.txt`

**Result: CEREG=3 immediately at 2 s** — same roaming-denial pattern as green.

**Revisão importante da hipótese §5.5:** O SIM E **não** é apenas 2G. Ele está provisionado para
**apenas LTE-M** (mesmo perfil do SIM D em ciano). O erro CEREG=ERROR observado nos testes NB-IoT agora está
explicado: o SIM não possui provisionamento NB-IoT, portanto o subsistema EPS do NB-IoT não
inicializa → `AT+CEREG` retorna ERRO. Ao alternar para o modo LTE-M (CMNB=1), o EPS
inicializa corretamente e o modem tenta se conectar ao LTE-M — o que é negado pela
rede (roaming na TIM).

| SIM | Resultado NB-IoT | Resultado LTE-M | Conclusão do perfil |
|-----|--------------|--------------|-------------------|
| A 🟡 TIM | ✅ CEREG=1 | ❌ CEREG=2 | **NB-IoT only** |
| B 🔴 Vivo | ❌ CEREG=3 | ⏳ pending | NB-IoT + LTE-M? |
| C 🟢 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **NB-IoT + LTE-M** |
| D 🩵 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **LTE-M only** |
| E 🩷 Vivo | ❌ CEREG=ERROR | ❌ CEREG=3 | **LTE-M only** (no NB-IoT) |

### 11.4 Teste Vivo Datatem LTE-M (SIM B 🔴 Vermelho) — concluído ❌

**Arquivo de log:** `M2M_VIVO_LTE-M_B28_red.txt`

**Resultado: CEREG=3 em 2 s → CEREG=2 a partir de 14 s → tempo limite excedido.** O modem encontrou
a célula LTE-M da TIM instantaneamente, teve a conexão negada (roaming) e, em seguida, procurou uma célula residencial da Vivo
durante os 166 s restantes, sem encontrar nenhuma. Mesmo padrão do teste externo em ciano (§10.3).

O vermelho está provisionado para NB-IoT e LTE-M (consistente com o verde), mas nenhuma das
tecnologias consegue se registrar porque a Vivo não possui infraestrutura em nenhuma das bandas nesta área.

### 11.5 Resumo do Perfil Final do SIM

| SIM | NB-IoT B28 | LTE-M B28 | Perfil de tecnologia | Causa raiz da falha |
|-----|-----------|-----------|-------------------|-----------------------|
| A 🟡 TIM | ✅ **HTTP 200** | ❌ CEREG=2 | **NB-IoT only** | No TIM LTE-M cell in area |
| B 🔴 Vivo | ❌ CEREG=3 | ❌ CEREG=3→2 | NB-IoT + LTE-M | No Vivo cell; TIM cell denied |
| C 🟢 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | NB-IoT + LTE-M | No Vivo cell; TIM cell denied |
| D 🩵 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **LTE-M only** | Roaming disabled; no Vivo LTE-M cell |
| E 🩷 Vivo | ❌ CEREG=ERROR | ❌ CEREG=3 | **LTE-M only** (no NB-IoT) | Roaming disabled; no Vivo LTE-M cell |

---

## 12. Conclusão Final — Problema nº 37

### 12.1 Resultado

**A tecnologia TIM Datatem NB-IoT é a única tecnologia celular viável para o gateway SAPI
em Cachoeira do Bom Jesus, Florianópolis, SC.**

| Aspecto | Conclusão |
|--------|-----------|
| **Working SIM** | SIM A 🟡 Yellow — TIM Datatem (`iot.datatem.com.br`) |
| **Working technology** | NB-IoT (`AT+CMNB=2`) |
| **Primary band** | Band 28 — 700 MHz ✅ HTTP 200 (§5.2) |
| **Backup band** | Band 3 — 1800 MHz ✅ HTTP 200 (§5.6) |
| **Payload** | 212 bytes MessagePack, HMAC-SHA256 signed |
| **Server response** | HTTP 200, data stored in production DB |

### 12.2 Por que todos os SIMs da Vivo falharam

Todos os cinco SIMs da Vivo (B, C, D, E) falharam neste local pelo mesmo motivo fundamental:
**não há infraestrutura NB-IoT ou LTE-M da Vivo na área.** As únicas células IoT visíveis pertencem à TIM. Os SIMs da Vivo não podem usar a rede NB-IoT/LTE-M da TIM (os acordos de roaming para essas tecnologias não estão habilitados entre as operadoras no Brasil).

O SIM pessoal M2M da Vivo (D) também tem o roaming de dados explicitamente desativado no portal da Plataforma Kite, o que o impediria de usar a infraestrutura da TIM mesmo que existisse um acordo de roaming.


### 12.3 Recomendação de Produção

**Configuração multibanda confirmada funcionando** (04/03/2026): `AT+CBANDCFG="NB-IOT",28,3`
permite que o modem selecione automaticamente a melhor banda disponível. Nos testes,
conectou-se à Banda 28 (sinal mais forte) com CSQ 22 — melhor que o teste de banda única
Banda 28 (CSQ 18). Log: `M2M_TIM_LTE-M_Multiband_yellow.txt`.

O backup celular do gateway SAPI (`gateway-01`) deve usar:

```cpp
// Configuração de backup celular de produção
#define IOT_MODE        "NB-IoT"
#define IOT_CMNB        2                        // AT+CMNB=2
#define IOT_BAND        "28,3"                   // Modem auto-selects best band
#define IOT_BAND_LABEL  "Band 28 + Band 3 (auto)"
const char apn[]      = "iot.datatem.com.br";
const char gprsUser[] = "datatem";
const char gprsPass[] = "datatem";
```

#### Multibanda AT+CPSI? resultado

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508013,260,EUTRAN-BAND28,9362,0,0,-12,-82,-70,20
```

| Metric | Band 28 only (§5.2) | **Multiband auto** | Change |
|--------|--------------------|--------------------|--------|
| Band selected | EUTRAN-BAND28 | EUTRAN-BAND28 | Same — B28 is best |
| CSQ | 18 | **22** | +4 ↑ |
| RSRP | −89 dBm | **−82 dBm** | +7 dB ↑ |
| RSSI | −87 dBm | **−70 dBm** | +17 dB ↑ |
| RSSNR | 19 dB | **20 dB** | +1 dB ↑ |

### 12.4 Itens em Aberto

| Item | Prioridade | Observações |
|------|----------|-------|
| Implementar backup celular NB-IoT no firmware de produção `gateway-01` | Alta | Usar o SIM A da TIM Datatem; Banda 28 primária, Banda 3 como fallback |
| Adicionar fila offline (SQLite) para buffer de pacotes durante interrupções de Wi-Fi | Alta | Backup celular útil apenas se não houver perda de pacotes durante a troca |
| Contatar o suporte M2M da Vivo para habilitar o roaming no SIM D (ciano) | Baixa | Opcional; necessário apenas se o SIM da TIM Datatem estiver indisponível |
| Testar novamente os SIMs da Vivo Datatem (B, C) em um local com cobertura NB-IoT da Vivo | Baixa | Confirmaria se o provisionamento do SIM está correto; não é necessário para a implementação do SAPI |

*Última atualização: 04/03/2026 — Todos os testes concluídos. Problema nº 37 resolvido.*

---

## 13. Diferenças entre os SIMs Vivo Datatem (B 🔴 Vermelho vs C 🟢 Verde)

Embora B e C sejam nominalmente idênticos (mesma operadora, mesmo provedor de APN, mesmo
tipo de provisionamento), seus padrões de falha diferem em dois testes:

| Teste | B 🔴 Vermelho | C 🟢 Verde | Interpretação |
|------|---------|-----------|----------------|
| Banda NB-IoT 28 | ❌ CEREG=3 | ❌ CEREG=3 | Idêntico — ambos encontram a célula da TIM, ambos negam |
| **Banda NB-IoT 3** | ❌ **CEREG=3** | ❌ **CEREG=2** | **Diferente** — Vermelho encontra uma célula da Banda 3; Verde não encontra nenhuma |
| Banda LTE-M 28 | ❌ CEREG=3→2 | ❌ CEREG=3 | Ligeiramente diferente — Vermelho perde a célula após a recusa; Verde permanece recusado |

### Diferença principal — NB-IoT Banda 3

- **Vermelho CEREG=3**: o modem encontrou uma célula NB-IoT Banda 3 (possivelmente uma célula Vivo visível
naquela direção) e enviou uma solicitação de conexão que foi rejeitada
- **Verde CEREG=2**: o modem escaneou toda a janela de 180 s e não encontrou nenhuma célula Banda 3

Isso sugere que o chip Vermelho pode ter uma sensibilidade ligeiramente melhor à Banda 3 ou foi posicionado
de forma diferente durante o teste, detectando brevemente uma célula da Vivo (ou da TIM) na Banda 3 que o chip Verde
não conseguiu detectar. Ambos os testes terminam em falha, mas o CEREG=3 do chip Vermelho na Banda 3 é um resultado mais interessante
— significa que existe uma célula da Banda 3 nas proximidades e, **se a Vivo habilitasse o roaming ou
se um chip fornecido pela TIM fosse usado, o NB-IoT da Banda 3 seria registrado com sucesso**
(confirmado pelo SIM A 🟡 na Banda 3 §5.6).

### Diferença LTE-M

O chip Vermelho transita de CEREG=3 para 2 (encontra a célula LTE-M da TIM, é rejeitado e, em seguida, nenhuma célula da Vivo é encontrada),
enquanto o chip Verde permanece em CEREG=3 o tempo todo. Isso é consistente com o chip Vermelho sendo testado
um pouco mais tarde, quando a célula LTE-M da TIM pode ter tido um sinal mais forte momentaneamente.

Não se trata de uma diferença de provisionamento — ambos os SIMs se comportam de forma idêntica em princípio.
---

## 14. Lista de verificação — Possíveis soluções para SIMs Vivo Datatem

Os chips Vivo Datatem (B 🔴, C 🟢, E 🩷) apresentam falhas constantes devido à ausência de infraestrutura NB-IoT da Vivo no gateway SAPI e à não permissão de roaming na rede TIM.
As seguintes ações podem resolver o problema, em ordem de probabilidade e facilidade.

Sources consulted: [Datatem NB-IoT/LTE-M](https://datatem.com.br/nb-iot-e-lte-m/) ·
[Datatem M2M Chip & APN](https://datatem.com.br/chip-m2m-apn-privada/) ·
[Datatem NB-IoT/CAT-1/CAT-M1](https://datatem.com.br/nb-iot-cat-1-e-cat-m1/)

---

### ✅ Solução 1 — Solicite um chip Multioperadora (Multi-MVNO) da Datatem ⭐ Maior probabilidade de funcionar

- [ ] Entre em contato com a Datatem e solicite um **chip M2M multioperadora** (também chamado de chip
multioperadora ou multi-MVNO)
- A Datatem oferece chips que podem alternar entre **TIM, Vivo e Claro**

automaticamente, selecionando o melhor sinal disponível em cada local
- Com um chip multioperadora, o modem se conectaria à célula NB-IoT da TIM (Banda 28 ou
Banda 3) no local SAPI sem qualquer restrição de roaming
- Mesmo APN (`iot.datatem.com.br`), mesmas credenciais — **nenhuma alteração de firmware necessária**
- A Datatem oferece análise de cobertura gratuita por tecnologia e local antes da compra

> **Contato**: [datatem.com.br](https://datatem.com.br/) — suporte técnico gratuito
> inclui análise de cobertura por tipo de tecnologia para o seu endereço específico.
---

### ✅ Solução 2 — Substituir chips Datatem da Vivo por chips Datatem da TIM

- [ ] Solicitar chips provisionados pela TIM à Datatem (mesmo APN, operadora TIM)
- O NB-IoT da TIM funciona **tanto na Banda 28 quanto na Banda 3** neste local (confirmado pelo SIM A)
- A TIM tem cobertura NB-IoT em **5.167 municípios** contra 4.006 da Vivo (junho de 2024,
fonte: Teleco) — cobertura NB-IoT mais ampla em nível nacional
- Mesmo APN `iot.datatem.com.br` — nenhuma alteração de firmware necessária
- **Isso já foi validado**: o SIM A 🟡 é um chip Datatem da TIM e funciona perfeitamente

---

### 🔧 Solução 3 — Contate o suporte da Datatem para diagnosticar o roaming do chip Vivo

- [ ] Abra um chamado de suporte com a Datatem descrevendo as falhas CEREG=3 nas bandas NB-IoT
28 e 3 dos chips Vivo
- Forneça: CCIDs dos chips, localização (coordenadas GPS), modelo do modem (SIM7000G), saída AT+CPSI
do teste TIM em funcionamento para referência
- Pergunte especificamente: *"O chip Vivo está habilitado para roaming nacional NB-IoT na
infraestrutura TIM?"*
- A Datatem gerencia acordos de roaming e pode habilitar o roaming em chips Vivo existentes
sem substituí-los
- **A Datatem oferece suporte técnico gratuito**, incluindo configuração de conectividade em dispositivos

---

### 🔧 Solução 4 — Verifique o mapa de cobertura NB-IoT da Vivo para o endereço específico

- [ ] Consulte a Datatem (ou verifique o portal de cobertura da Vivo) para obter informações sobre a cobertura NB-IoT nas
coordenadas GPS exatas: **27°25'53"S, 48°25'18"W** (Cachoeira do Bom Jesus, Florianópolis)
- A Vivo possui NB-IoT em 4.006 municípios — mas a cobertura municipal não garante
cobertura em nível de rua; uma torre deve estar dentro do alcance.
- Se a Vivo não tiver uma célula NB-IoT a aproximadamente 5 km do local, nenhuma alteração de firmware ou SIM
resolverá o problema — somente as Soluções 1 ou 2 se aplicam.
- O CEREG=3 consistente na Banda 28 (e não CEREG=2) sugere que uma célula da Vivo **pode existir
nas proximidades**, mas o SIM não está autorizado a roaming — vale a pena confirmar antes de substituir os chips.
---

### 🔧 Solução 5 — Habilitar roaming de dados nacional no SIM D do Vivo M2M pessoal 🩵 Ciano

- [ ] Entre em contato com o suporte comercial do Vivo M2M e solicite: *"Ativar tráfego de dados em
roaming nacional no ICC <ICCID>"*
- A opção "Ativar roaming de dados" na plataforma Kite requer um perfil de Administrador
— o suporte da Vivo pode habilitá-la diretamente
- Uma vez habilitada, o SIM D deve se registrar na célula LTE-M Banda 28 da TIM (consistentemente visível
no local interno — CEREG=3 significa que a célula está presente)
- Isso resolve apenas o problema do SIM D (chip pessoal) — não corrige o problema dos chips Datatem (B, C, E)
- **Observação sobre custos**: o roaming nacional pode incorrer em custos adicionais — confirme com o suporte do Vivo M2M

---

### 🧪 Solução 6 — Teste os chips Vivo Datatem em um local com cobertura NB-IoT da Vivo confirmada

- [ ] Use o verificador de cobertura da Vivo para encontrar um local próximo com cobertura NB-IoT da Vivo confirmada
- Pegue o gateway (com o chip B 🔴 ou C 🟢) e teste a Banda 28 do NB-IoT
- Se CEREG=1 (residência registrada), o SIM está provisionado corretamente e o problema é
puramente geográfico (nenhuma torre Vivo no local de instalação do SAPI)
- Esta etapa de diagnóstico confirmaria se vale a pena seguir as Soluções 3/4 em vez de
ir diretamente para as Soluções 1/2
- O valor notável **CEREG=3 para Vermelho na Banda 3** (§13) significa que uma célula foi encontrada — testar o Vermelho
em uma área de cobertura Vivo mais forte na Banda 3 seria particularmente informativo
---

### Resumo

| # | Solução | Esforço | Custo | Recomendado |
|---|----------|--------|------|-------------|
| 1 | Chip multioperador da Datatem | Baixo — contato + troca de SIM | Custo do novo chip | ⭐ **Sim — melhor opção** |
| 2 | Chip TIM Datatem (já validado) | Baixo — contato + troca de SIM | Custo do novo chip | ✅ Sim — comprovadamente funciona |
| 3 | Suporte da Datatem para habilitar o roaming em chips existentes | Baixo — chamado de suporte | Nenhum | ✅ Tentar primeiro |
| 4 | Verificar o mapa de cobertura NB-IoT da Vivo | Muito baixo — uma consulta | Nenhum | ✅ Diagnóstico rápido |
| 5 | Habilitar o roaming no SIM pessoal D da Vivo (ciano) | Baixo — ligar para a Vivo M2M | Possível custo adicional | Opcional |
| 6 | Teste de campo dos chips da Vivo em um local com cobertura da Vivo | Médio — teste físico | Nenhum | Apenas diagnóstico |
