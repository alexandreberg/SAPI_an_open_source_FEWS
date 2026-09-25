# Recalibração dos limiares e reconstrução do catálogo — Issue #225 (2026-09-09)

*Complementa `lead_time_horizontes_longos_investigacao.md` (Issue #223, viés de treino).
Aquela correção arrumou **como** o modelo era treinado; esta arruma **contra o que** ele é
avaliado.*

## 1. A linha de base do rio não é estacionária

| Estação-01 | Mediana | p90 | % do tempo ≥45 cm | % ≥50 cm |
|---|---|---|---|---|
| jul/2025 | 29 cm | 32 cm | 0 % | 0 % |
| dez/2025 | 35 cm | 42 cm | 8,3 % | 4,5 % |
| abr/2026 | 39 cm | 48 cm | 23,6 % | 6,6 % |
| jul/2026 | **45 cm** | 49 cm | **54,4 %** | 9,5 % |
| set/2026 | **47 cm** | 58 cm | **74,2 %** | **32,3 %** |

Subida de ~18 cm em 14 meses. A Estação-03 confirma: mediana de 50 cm em setembro,
acima de 45 cm 100 % do tempo. Como são **instrumentos diferentes medindo a mesma
água**, a concordância descarta deriva de instrumento — a subida está no rio. De maio a
setembro a E01 subiu +7,0 cm e a E03 +8,0 cm; se fosse artefato do sensor não
compensado da E01, ela teria subido *mais*, não menos.

**Consequência**: os limiares de 50/60/75 cm ficaram sem significado uniforme. Em
jul/2025 os 50 cm estavam 21 cm acima da mediana; em set/2026, 3 cm — e eram
ultrapassados 31 % do tempo. Deixaram de separar evento de escoamento normal.

## 2. Novos limiares: 60 / 75 / 90 cm

Escolhidos sobre a distribuição dos 42 episódios de dez/2024 a set/2026, ancorados nas
descontinuidades naturais em vez de números redondos:

```
162, 101, 101, 98, 97 │ 84, 79, 77, 75, 74 │ 69 ... 60 │ 59 ... 45
                       ↑ vão de 13 cm       ↑ vão de 5 cm
```

| Limiar | Eventos | Treino | Teste | % do tempo acima em set/26 |
|---|---|---|---|---|
| Atenção 60 cm | 23 | 16 | 7 | 9,0 % |
| Alerta 75 cm | 9 | 6 | 3 | 2,8 % |
| Inundação 90 cm | 5 | 3 | 2 | 1,1 % |

Qualquer valor entre 85 e 96 cm seleciona os mesmos 5 eventos maiores; 90 foi escolhido
por coincidir com a Atenção do sistema operacional, criando ponte entre a escala de
avaliação e a de alerta real.

**Os limiares são fixos por princípio.** Uma estação hidrometeorológica não move seus
níveis de alerta entre anos secos e chuvosos. A deriva da base fica documentada como
limitação, não é compensada.

**Trocar limiar não exige retreinar.** Os modelos preveem nível em centímetros; os
limiares entram depois, onde previsão vira alerta. Mudá-los re-roda os scripts de
avaliação, nunca o treino. Isso viabiliza um controle de operador para esses níveis,
ajustando-os em direção aos estágios reais à medida que o histórico cresce — registrado
aqui para virar requisito rastreável.

## 3. Detecção de episódios por amplitude, não por magnitude absoluta

Com a base derivando, um corte fixo se comporta de forma completamente diferente nas
duas pontas do registro. A 45 cm o detector devolveu **133 "eventos"**, 112 deles em
2026, pico mediano de 46 cm, alguns durando 11 dias — estava rastreando fluxo normal.

`build_event_catalogue.py` segmenta por **amplitude ≥12 cm sobre a mediana móvel de 7
dias**. Isso é dispositivo de recorte, não limiar: decide onde um episódio começa e
termina; os níveis de alerta seguem absolutos e o campo `level` sai deles.

Os dois critérios concordam no registro atual (31 eventos por absoluto ≥55 cm contra 36
por amplitude ≥15 cm, mesmo pico mediano de 65–66 cm nos dois anos), o que é o argumento
de que o limiar fixo continua defensável apesar da deriva.

`flash_flood` passa a ser decidido por taxa de subida ≥50 cm/h em 30 min, calibrada
contra os rótulos do v2: os três casos inequívocos atingem 67,9 / 70,5 / 155,0 cm/h
contra 32,0 da cheia gradual mais rápida. Isso reclassifica o E05 do v2 como `flood` —
ele mede 8,0 cm/h na própria janela, tendo herdado o rótulo do episódio do qual foi
separado.

**Catálogo v3: 35 episódios, 26 treino / 9 teste** (`event_windows_v3.csv`).

## 4. Emenda das lacunas da E01 com a E03

A Estação-01 ficou fora do ar de 13 a 16 de agosto (zero leituras) para conserto de
hardware, mais falhas parciais em 06, 07, 09, 10, 12 e 17 — exatamente durante os
maiores eventos de agosto, que a E03 registrou.

| | Cobertura (mai–set) | Maior lacuna |
|---|---|---|
| E01 sozinha | 93,6 % | **120,6 h** |
| E03 sozinha | 91,7 % | 44,3 h |
| **E01 ou E03** | **99,5 %** | — |

As lacunas quase não coincidem. **Redundância de estação leva a disponibilidade de
93,6 % para 99,5 %** — resultado de engenharia citável, e argumento direto a favor de o
projeto ter duas estações de cota.

### 4.1 Offset por faixa, não constante

| Faixa | n | Offset (E03 − E01) |
|---|---|---|
| 0–50 cm | 35.216 | **+2,00** |
| 50–60 cm | 4.030 | +2,00 |
| 60–75 cm | 1.026 | +1,00 |
| 75–90 cm | 265 | **−0,75** |
| ≥90 cm | 56 | **−1,80** |

A E01 lê progressivamente mais alto em relação à E03 conforme o rio sobe, invertendo o
sinal em cota de cheia. **Isso tem causa física**: a única régua linimétrica está
parafusada embaixo da E03; a E01 fica 30 m a montante, mais perto da chegada da água,
onde a superfície é mais turbulenta durante cheias. Um HC-SR04 sem compensação lendo
superfície agitada retorna o eco forte mais próximo — a crista de uma onda — e portanto
superestima o nível, tanto mais quanto mais agitada a superfície.

Isso **reconcilia a tabela de validação por régua com as estatísticas de sobreposição**:
o +2,65 cm da régua para a E01 vem de 26 leituras ponderadas para dias de inundação,
enquanto o +2,00 cm da sobreposição reflete as condições ordinárias que dominam o
registro. Os dois medem regimes diferentes, não se contradizem.

Validação cruzada em 5 blocos temporais:

| Método | REQM global | REQM ≥70 cm | Viés ≥70 cm |
|---|---|---|---|
| Constante | 2,58 | 4,10 | **−2,23** |
| **Por faixa** | 2,64 | **3,36** | **−0,02** |
| Regressão linear | 2,86 | 5,52 | −4,31 |

Escolher pelo REQM global escolheria errado. O offset por faixa é marginalmente pior no
global e decisivamente melhor onde a emenda é usada. **Isso mudou o E33 de 88 para
92 cm, ou seja de Alerta para Inundação.**

### 4.2 Proveniência é gravada

A lacuna está no período de **teste**, então um valor preenchido não é só entrada do
modelo — é a verdade contra a qual ele é pontuado. Cada amostra carrega `source` e cada
linha do catálogo carrega `donor_pct`.

Contexto que relativiza a ressalva: contra a régua, a **E01 tem REQM de 4,04 cm e viés
de +2,65 cm** (n=26), contra 0,90 / +0,40 da E03 (n=5). O resíduo de ~3,3 cm da emenda
**não é pior que o erro de medição da própria série hospedeira**. As colunas de
proveniência são transparência, não sinal de dado inferior. Qualquer evento a menos de
~4 cm de um limiar está dentro da incerteza instrumental, preenchido ou não.

A E01 segue como referência **por antiguidade de série, não por qualidade metrológica**:
20 meses contra 6 da E03, que é o instrumento calibrado e compensado.

## 5. Métricas finais

> **Atualização (2026-09-11, Issue #227):** os números desta seção são anteriores à
> exclusão dos 9 eventos que eram artefato de sensor (E09, E13–E17, E19, E21, E23) e à
> remoção desses trechos do treino. Os valores vigentes estão em
> `artefatos_catalogo_v3.md`, Seção 6. Resumo: o M6 melhora em todos os horizontes fora
> da amostra, e em Inundação passa a detectar os 3 eventos de teste em cima da hora; o M4
> fica igual. A conclusão da §5.3 (nenhum modelo antecipa em Inundação) continua valendo.

### 5.1 Calibração fora da amostra (37.857 passos, mai–set/2026)

| Modelo | Horiz. | Viés | REQM | Previsto ≥60 cm | Observado |
|---|---|---|---|---|---|
| M4 | +30 | −0,16 | 1,02 | 4,69 % | 5,15 % |
| M4 | +120 | −0,52 | 2,50 | 3,79 % | 5,16 % |
| M6 | +30 | −0,19 | **0,80** | 4,87 % | 5,15 % |
| M6 | +120 | −0,67 | **2,32** | 4,44 % | 5,16 % |

Viés levemente **negativo**, crescente com o horizonte: os modelos subestimam um pouco.
Lado seguro para REQM, não para alarme.

**Fora da amostra o M6 vence em todos os horizontes.** Na simulação completa o M4
aparece melhor (1,05 contra 1,22 em +30), mas isso é ajuste dentro da amostra — ali o M4
faz 0,77 contra 1,31 do M6. Qualquer afirmação de desempenho relativo deve citar a
métrica fora da amostra, de `scan_audit_findings.py --calibration`.

### 5.2 Alarme operacional (debounce 3 passos / 15 min)

| Modelo | Limiar | VP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|
| M4 | Atenção 60 | 19 | 7 | 4 | 0,731 | 0,826 | 0,776 |
| M4 | Alerta 75 | 9 | 1 | 1 | 0,900 | 0,900 | 0,900 |
| M4 | Inundação 90 | 4 | 0 | 2 | 1,000 | 0,667 | 0,800 |
| M6 | Atenção 60 | 20 | 4 | 3 | 0,833 | 0,870 | 0,851 |
| M6 | Alerta 75 | 9 | **0** | 1 | **1,000** | 0,900 | **0,947** |
| M6 | Inundação 90 | 5 | **0** | 1 | **1,000** | 0,833 | **0,909** |

### 5.3 Limitação central: no nível mais alto não há antecipação

| Evento | M4 Inundação (90 cm) | M6 Inundação (90 cm) |
|---|---|---|
| E31 (97 cm) | **nunca previu** | −5 / −20 / −20 / −35 min |
| E33 (92 cm) | −60 min | 0 / −5 / — / — |
| E35 (101 cm) | **nunca previu** | 0 / −15 / −15 / −15 min |

**O M4 não alcança o limiar de 90 cm nas previsões** (2 falsos negativos de 3 eventos).
**O M6 alcança, mas avisa em cima da hora ou atrasado** — todos os lead times ≤0.

Em Alerta o M4 antecipa de verdade (0 a 75 min) enquanto o M6 é sistematicamente
negativo (−5 a −15 min). Resumindo: **o M4 antecipa quando avisa, mas falha em avisar; o
M6 quase nunca falha em detectar, mas praticamente não antecipa.**

Isso é consequência direta de a calibração ter sido corrigida. O viés positivo antigo
produzia "antecipação" porque o modelo vivia acima do limiar; removido o viés, aparece o
que o modelo de fato consegue — e no extremo superior ele rastreia em vez de antecipar.

## 6. Comparabilidade

Os números aqui **não são comparáveis** aos anteriores à Issue #225: mudaram os limiares
(50/60/75 → 60/75/90), o corte de treino (fev → mai/2026), o catálogo (20 curados à mão
→ 35 segmentados) e a série de nível (com emenda). A única comparação limpa antes/depois
é a do PR #224, restrita aos mesmos instantes fora da amostra.

## 7. Reprodução

```bash
cd predictive-models/
V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3

# 1) dump novo -> CSVs por estação (usa o venv de predictive_model, que tem dotenv)
../predictive_model/.venv/bin/python3 ../predictive_model/00_load_sql_dump.py \
    /home/ilha3d/SAPI/DB/<dump>.sql

# 2) filtro de 3 passes da Issue #211
$V reprocess_level_spike_return_filter.py

# 3) emenda com a E03 (lê o corrigido, escreve o gapfilled)
$V build_gapfilled_level.py

# 4) catálogo
$V build_event_catalogue.py

# 5) modelos (M6 ~5 min, M4 ~25 min no RPi)
(cd results_final_m6_mlr && $V 01_model6_mlr_continuous.py)
(cd results_final_m4_lgbm && $V 01_model4_continuous.py)

# 6) métricas
(cd results_final_m4_lgbm && $V 04_lead_time_m4.py)
(cd results_final_m6_mlr  && $V 04_lead_time_m6.py && $V 05_rmse_per_event.py && $V 06_compare_fullsim.py)
$V scan_audit_findings.py --calibration

# 7) PDF de auditoria + chuva acumulada (~4 min, o parsing do dump domina)
$V plot_events_audit_pdf.py
```

**Armadilha**: `config.LEVEL_CSV` aponta para a *saída* do `build_gapfilled_level.py`.
Esse script usa `HOST_CSV` explícito para não ler o próprio resultado. Não troque por
`config.LEVEL_CSV`.

## 8. Chuva acumulada antes do pico (PDF de auditoria, 2026-09-11)

`plot_events_audit_pdf.py` regenera `output_audit/auditoria_eventos_A3.pdf` para os 35
eventos (72 páginas) e imprime, no cabeçalho de cada evento e em três colunas do
catálogo, a chuva acumulada nas 6, 12 e 24 h anteriores ao pico catalogado. A tabela
também sai em `output_audit/precip_acumulada_eventos.csv`.

- **Fonte**: a mesma série de 5 min que alimenta M4/M6 (`real_utils.load_real_data()`):
  MERGE antes de 02/01/2026, Estação-02 depois. Soma dos passos em (pico − H, pico].
- **Cobertura**: o pipeline preenche falta de dado, então 0 mm pode ser ausência de dado.
  O script marca com `*` as janelas com lacuna na fonte — Estação-02 com intervalo entre
  leituras > 30 min (a falta vira 0 mm) ou hora MERGE ausente (o `ffill` repete a hora
  anterior). Marcados: E02 e E11 (MERGE, 5 h e 1 h; efeito ≤0,1 mm), E22 (1h46), E23
  (6h46) e E33 (48 min) na Estação-02.

**Achado**: oito eventos têm ≤0,8 mm nas 24 h antes do pico — E13, E14, E15, E16, E17,
E19, E21 e E23 — e só o E23 com lacuna na fonte. Todos estão no conjunto de treino. No
E14 (74 cm, tipo enxurrada) e no E23 o nível bruto alterna em degraus quadrados entre a
linha de base e ~50–74 cm, o padrão de eco do HC-SR04 da Issue #211, e o degrau passa
pelo filtro. Os demais ainda precisam de inspeção visual nas Páginas A. Se confirmados
como artefato, são episódios de sensor, e não de cheia, dentro do catálogo e do treino.
