# Artefatos de sensor no catálogo v3 — exclusão e remoção do treino (Issue #227, 2026-09-11)

> Resumo das decisões e dos números vigentes para a dissertação:
> `base_reescrita_dissertacao.md`.

## 1. Como foi encontrado

O PDF de auditoria (`output_audit/auditoria_eventos_A3.pdf`) foi regenerado para o
catálogo v3 (35 eventos) com uma informação nova por evento: a chuva acumulada nas
6, 12 e 24 h anteriores ao pico, somada da mesma série que alimenta M4/M6 (MERGE
antes de 02/01/2026, Estação-02 depois). Ver `limiares_e_catalogo_v3.md`, Seção 8.

Com isso, o autor fez a inspeção visual de todos os eventos, comparando o nível
bruto com o filtrado. O resultado está na Seção 2.

## 2. Inspeção visual, evento a evento (nível bruto × filtrado)

| Evento | Observação do autor | Classificação |
|---|---|---|
| E01, E02, E04, E05, E08, E10, E18 | Pequena queda do nível logo antes da subida (Seção 7) | Evento real |
| E09 | Nível bruto muito ruidoso; o ruído somado criou uma falsa elevação | **Artefato** |
| E11 | Quatro picos espúrios passaram pelo filtro | Evento real, com ruído residual |
| E12 | Dado faltante antes da subida; queda antes de subir | Evento real |
| E13, E14, E15, E16, E17, E19, E21, E23 | Outliers do bruto agrupados pelo filtro numa falsa subida; chuva zero | **Artefato** |
| E20 | Pico espúrio na descida; subida correta | Evento real |
| E22, E24 | Muito ruidosos; picos negativos não filtrados (E22 tem um pico positivo já na descida) | Evento real, com ruído residual |
| E25 | Dois picos distintos; alguns picos espúrios, positivos na subida | Evento real, com ruído residual |
| E26, E34 | Filtragem correta | Evento real |
| E32, E33 | Quase sem Estação-01 no bruto — série vinda da Estação-03 (87 % e 93 % da janela) | Evento real |
| E35 | Cinco picos em cerca de 12 h | Evento real |

O ruído que passa pelo filtro (E11, E20, E22, E24, E25) é tratado na Issue #228.
Os eventos com vários picos são tratados na Issue #229.

## 3. Premissa física

Conhecimento de campo do autor, que mora no local: **não existe inundação ali sem
chuva** de uma certa intensidade ou duração. Pelo barulho e pela intensidade da chuva,
ele consegue estimar se haverá risco de inundação. Logo, uma subida de nível sem chuva
registrada é um artefato de sensor ou uma falha no dado de precipitação, e nunca uma
cheia sem chuva.

## 4. Regra de exclusão

| Período | Fonte da chuva | Regra |
|---|---|---|
| A partir de 02/01/2026 (janela de 24 h inteira) | Estação-02, pluviômetro no local | Chuva em 24 h antes do pico < 5 mm → artefato, **automático** |
| Antes de 02/01/2026 | MERGE (satélite) | Só por **inspeção visual**, lista explícita no código (E09) |

**Validação.** A regra reproduz exatamente os 9 artefatos da inspeção visual. O único
evento extra que ela marcaria é o E12 (3,7 mm, período MERGE), que visualmente não é
artefato — e por isso a regra não é aplicada automaticamente no período MERGE.

**Por que o MERGE não pode decidir sozinho.** O E04 é uma cheia real de 98 cm com
só 5,3 mm em 24 h no MERGE. Nessa época não havia nem a Estação-02 nem o pluviômetro
de copo. Comparações anteriores já mostravam o MERGE errando o horário da chuva ou não
registrando chuva que houve.

**Por que 24 h e não 6 h.** Com 6 h, o E22 (evento real) seria excluído. A Estação-02
mediu 46 mm entre 00h e 06h de 20/03/2026 e depois ficou **sem leituras de 08h21 a
10h07**, justamente quando o MERGE registrou 4,8 + 4,0 mm. Nas 6 h antes do pico
(12h25), a série do modelo marca 0 mm. Neste caso quem perdeu a chuva foi o
pluviômetro, na lacuna, e não o MERGE.

**Eventos excluídos**

| Evento | Pico (UTC) | Pico (cm) | Chuva em 24 h (mm) | Fonte | Critério |
|---|---|---|---|---|---|
| E09 | 2025-12-26 23:25 | 59 | 1,6 | MERGE | Inspeção visual |
| E13 | 2026-01-05 05:00 | 58 | 0,0 | Estação-02 | Automático |
| E14 | 2026-01-08 09:45 | 74 | 0,0 | Estação-02 | Automático |
| E15 | 2026-01-16 06:10 | 68 | 0,0 | Estação-02 | Automático |
| E16 | 2026-01-17 09:10 | 69 | 0,0 | Estação-02 | Automático |
| E17 | 2026-01-18 03:35 | 69 | 0,8 | Estação-02 | Automático |
| E19 | 2026-02-03 21:15 | 68 | 0,2 | Estação-02 | Automático |
| E21 | 2026-03-13 21:30 | 60 | 0,0 | Estação-02 | Automático |
| E23 | 2026-03-30 03:15 | 52 | 0,0 | Estação-02 | Automático (lacuna de 6h46 na janela, mas 0 mm nas janelas completas de 6 e 12 h) |

Os 9 continuam no `event_windows_v3.csv`, marcados com `split_set = excluded` e
`exclusion = artifact`, com o motivo nas notas. Assim a numeração E01–E35 não muda e
continua batendo com o PDF e com os documentos anteriores. Duas colunas novas:
`p24h_mm` e `exclusion`.

Catálogo resultante: **17 eventos de treino, 9 de teste e 9 excluídos**. Nenhum evento
de teste foi afetado: todos têm pelo menos 18,5 mm em 24 h.

## 5. Por que tirar do catálogo não basta — e o que foi feito

Desde a Issue #223, M4 e M6 treinam em modo contínuo: sobre a série de nível inteira
até `TRAIN_END` (01/05/2026), e não sobre as janelas do catálogo. Tirar os eventos do
catálogo deixaria os artefatos no treino, ensinando ao modelo que o nível pode subir
até 74 cm sem chuva, o que enfraquece justamente a variável que dá antecipação à
previsão.

O que foi implementado (`real_utils.py`, idêntico nas pastas M4 e M6):

1. **Série de nível.** `load_real_data()` apaga o nível dentro das janelas de análise
   dos eventos com `exclusion = artifact`: 813 passos de 5 min (cerca de 68 h). O resto
   da série fica idêntico.
2. **Treino.** `build_continuous_training_segment()` preenchia qualquer lacuna repetindo
   o último valor válido, o que pintaria um nível plano inventado no lugar do artefato.
   Agora o período de treino é dividido em **10 trechos contínuos** em volta das 9
   janelas, e os modelos são ajustados sobre a lista de trechos, sem dado inventado. O
   treino passou de 140.013 para 139.200 passos.
3. **Inferência.** `mask_artifact_rows()` apaga o observado e as previsões dos dois
   modelos dentro das janelas. O M6 preenche as próprias entradas para prever, então
   sem isso ele teria previsões sobre um trecho que não é nível de rio. As janelas ficam
   fora de todas as métricas e da simulação de alertas.
4. **Catálogo.** `build_event_catalogue.py` calcula a chuva de 24 h de cada episódio
   (`real_utils.load_precip_5min()`, a mesma série dos modelos) e aplica a regra da
   Seção 4. Uma chave da lista manual que deixe de corresponder a um episódio após uma
   reconstrução gera aviso, em vez de ser ignorada em silêncio.
5. **PDF de auditoria.** Os 35 eventos continuam no relatório. Os 9 excluídos aparecem
   com selo vermelho "EXCLUÍDO" e um aviso explicando que o trecho foi removido. O
   painel filtrado mostra o que foi removido.

## 6. Resultado — métricas antes e depois

**Comparação justa.** Os artefatos estavam todos no período de treino. No registro
inteiro, eles contavam como "eventos" (um alerta dentro deles era verdadeiro positivo) e
tinham erros grandes, então os números do registro inteiro mudam só porque os artefatos
saíram. A comparação abaixo usa apenas o **período fora da amostra (a partir de
01/05/2026)**, com os mesmos instantes e os mesmos 9 eventos de teste antes e depois.
A REQM segue a definição de `scan_audit_findings.py --calibration`.

### 6.1 REQM fora da amostra (cm) — 37.857 a 37.893 passos

| Modelo | +30 | +60 | +90 | +120 |
|---|---|---|---|---|
| M4 antes → depois | 1,02 → 1,05 | 1,66 → 1,65 | 2,11 → 2,11 | 2,50 → 2,55 |
| M6 antes → depois | 0,80 → **0,72** | 1,39 → **1,28** | 1,89 → **1,80** | 2,32 → **2,24** |

- **M6 melhora em todos os horizontes**, de 0,08 a 0,11 cm (4 a 10 %), e o viés negativo
  diminui (+120: −0,67 → −0,63 cm).
- **M4 fica igual:** variação de ±0,05 cm, dentro do ruído.
- A REQM média por evento de teste segue o mesmo padrão: M6 cai de 1,99 para 1,71 cm em
  +30 e de 6,27 para 6,04 em +120; o M4 fica praticamente igual (2,46 → 2,52; 6,11 → 6,22).

### 6.2 Alarme no período de teste (persistência de 3 passos = 15 min)

| Modelo | Atenção 60 (VP/FP/FN) | Alerta 75 | Inundação 90 |
|---|---|---|---|
| M4 antes | 8 / 1 / 0 | 4 / 0 / 1 | 1 / 0 / 2 |
| M4 depois | 8 / 1 / 0 | 5 / 1 / 0 | 1 / 0 / 2 |
| M6 antes | 6 / 0 / 2 | 4 / 0 / 1 | 2 / 0 / 1 |
| M6 depois | **7 / 0 / 1** | **5 / 0 / 0** | **3 / 0 / 0** |

O M6 passa a detectar todos os eventos de teste em Alerta e em Inundação, sem nenhum
falso alarme. O M4 ganha um acerto em Alerta, mas também um falso alarme, e continua sem
alcançar Inundação em 2 de 3 eventos.

### 6.3 Lead time em Inundação (min, horizontes +30 / +60 / +90 / +120)

| Evento | M4 antes | M4 depois | M6 antes | M6 depois |
|---|---|---|---|---|
| E31 (97 cm) | nunca previu | nunca previu | −5 / −20 / −20 / −35 | **+5 / −5 / −5 / −5** |
| E33 (92 cm) | −60 / — / — / — | −60 / −30 / — / — | 0 / −5 / — / — | 0 / 0 / −5 / −5 |
| E35 (101 cm) | nunca previu | −50 / — / — / — | 0 / −15 / −15 / −15 | **+5 / 0 / 0 / 0** |

Em Alerta, os lead times do M6 também sobem para perto de zero (E32 e E35: de −15 para
0 min até +90), e os do M4 continuam positivos (de +10 a +145 min).

**Leitura.** A limitação central registrada em `limiares_e_catalogo_v3.md` §5.3
continua: **em Inundação, nenhum modelo antecipa de fato.** Mas o M6 deixa de avisar
atrasado (até −35 min) e passa a avisar em cima da hora (−5 a +5 min) em todos os 3
eventos.

O ganho concentrado no M6 é coerente com o mecanismo descrito na Seção 5: um modelo
linear usa os mesmos coeficientes no registro inteiro, e subidas sem chuva no treino
puxavam para baixo o peso da precipitação. Árvores (M4) conseguem isolar essas regiões,
então sofriam menos. É uma interpretação plausível, ainda não verificada diretamente (por
exemplo, comparando os coeficientes de chuva do M6 antes e depois).

### 6.4 Instabilidade do lead time do M4

Com o retreino, 37 valores de lead time do M4 nos eventos de teste mudaram, alguns em
mais de 3 horas: no E30, Atenção em +90 foi de −30 para +175 min; no E34, de 0 para
+180 min. O painel +90 min do E34 (PDF, Página B) mostra a causa. O "cruzamento
previsto" é um **pico isolado** da previsão do M4 às 11h35, no meio de uma curva ruidosa,
e não uma antecipação sustentada.

O cálculo de lead time usa o primeiro instante em que a previsão toca o limiar, sem
exigir persistência. A análise de alarme exige 15 min seguidos. Valores de lead time
próximos do limite de causalidade (180 min) devem ser conferidos no PDF antes de serem
citados. A correção (exigir persistência também no cruzamento previsto) foi registrada
na Issue #229, que já revisa a regra de cruzamento.

### 6.5 Registro inteiro (referência — a população mudou)

| | M4 antes | M4 depois | M6 antes | M6 depois |
|---|---|---|---|---|
| REQM +30 (cm) | 1,053 | 1,003 | 1,215 | 0,971 |
| REQM +120 (cm) | 1,875 | 1,827 | 2,366 | 2,239 |

Alarme no registro inteiro, depois (persistência de 15 min):

| Modelo | Limiar | VP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|
| M4 | Atenção 60 | 17 | 8 | 0 | 0,680 | 1,000 | 0,810 |
| M4 | Alerta 75 | 10 | 2 | 0 | 0,833 | 1,000 | 0,909 |
| M4 | Inundação 90 | 4 | 0 | 2 | 1,000 | 0,667 | 0,800 |
| M6 | Atenção 60 | 16 | 4 | 1 | 0,800 | 0,941 | 0,865 |
| M6 | Alerta 75 | 10 | 1 | 0 | 0,909 | 1,000 | 0,952 |
| M6 | Inundação 90 | 6 | 0 | 0 | 1,000 | 1,000 | 1,000 |

Não compare estas contagens com a tabela anterior da §5.2 de
`limiares_e_catalogo_v3.md`: lá, os artefatos contavam como eventos a detectar.

## 7. A queda antes da subida

Em vários eventos o nível cai um pouco imediatamente antes de subir. Medindo a queda na
1,5 h anterior ao início da subida, em todos os eventos:

| Série | Queda média | Eventos com queda ≥ 2 cm |
|---|---|---|
| Bruto (mediana de 5 min, sem filtro) | 0,5 cm | 6 |
| Filtrado (o que alimenta os modelos) | 0,7 cm | 7 |
| Estação-03 (US-100), onde há dado | ≤ 1 cm | 0 |

- A queda, de 1,5 a 3 cm, **já está no dado bruto** (E01–E03, E08, E10, E18). Não é
  efeito de plotagem nem, na maioria dos casos, do filtro.
- **Exceção — E05:** no início da subida, o sensor soltou um pico alto (139 cm) junto
  com leituras baixas (26 e 30 cm; linha de base 33 cm). O filtro rejeitou o pico alto
  (salto maior que 40 cm), mas não as leituras baixas (só ~7 cm abaixo), e a média de
  5 min puxou o nível para 28,7 cm. O mesmo par alto + baixo aparece no E10.
- **Causa física não estabelecida.** A hipótese de resfriamento do ar pela chuva
  afetando o HC-SR04 (sem compensação de temperatura) não foi confirmada: a queda não
  aparece nos eventos de 2026 em nenhuma das estações, e a temperatura (medida em graus
  inteiros) não acompanha.
- Impacto pequeno (1,5 a 3 cm em cerca de 7 de 35 eventos). Registrado na Issue #228.

## 8. Pendências relacionadas

- **Issue #228** — redesenho do filtro. Rajadas e picos, positivos e negativos, ainda
  passam. Premissa do autor: o nível de um rio nunca varia bruscamente num intervalo
  curto, nem para cima nem para baixo. Discussão ainda aberta: Kalman, filtro secundário
  ou restrição física de taxa de variação.
- **Issue #229** — lead time por ocorrência de cruzamento de limiar, para eventos com
  vários picos (E25, E31, E33, E34, E35). A folga de reativação a comparar é de 5, 8 ou
  10 cm.
- **Produção.** `production/` ainda treina só com janelas de evento (pendência da
  #223). A remoção dos artefatos precisa acompanhar quando a produção for retreinada.

## 9. Reprodução

```bash
cd predictive-models/
V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3

$V build_event_catalogue.py                       # regra de exclusão -> event_windows_v3.csv
(cd results_final_m6_mlr && $V 01_model6_mlr_continuous.py)
(cd results_final_m4_lgbm && $V 01_model4_continuous.py)
(cd results_final_m4_lgbm && $V 04_lead_time_m4.py)
(cd results_final_m6_mlr  && $V 04_lead_time_m6.py && $V 05_rmse_per_event.py && $V 06_compare_fullsim.py)
$V scan_audit_findings.py --calibration
$V plot_events_audit_pdf.py
```
