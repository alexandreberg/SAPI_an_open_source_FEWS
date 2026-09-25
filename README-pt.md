# SAPI — Sistema de Alerta Prévio de Inundações

🇬🇧 [Read in English](README-en.md) · 🇧🇷 **Português**

Um sistema de alerta prévio de inundações baseado em LoRa: estações de nível d'água
(cota) e de pluviômetro enviam suas leituras a um gateway LoRa, que as encaminha a um
backend em nuvem, onde modelos de aprendizado de máquina preveem o nível do córrego e
emitem alertas por múltiplos canais.

> **Nota sobre o idioma.** O código, os comentários e a maior parte da documentação
> técnica deste repositório estão em inglês; alguns documentos em `docs/` estão em
> português, o idioma da dissertação que originou o projeto.

## O que é o SAPI?

O SAPI (*Sistema de Alerta Prévio de Inundações*) é uma plataforma de monitoramento e
alerta prévio de inundações, de baixo custo e código aberto, desenvolvida e validada como
projeto de mestrado. Ele endereça uma lacuna documentada: a efetividade dos sistemas de
alerta prévio de inundações depende da articulação entre conhecimento do risco,
monitoramento e previsão em tempo real, disseminação de alertas e capacidade de resposta —
componentes que países em desenvolvimento e pequenos municípios muitas vezes não têm
recursos para implementar por completo. O SAPI atua diretamente nos pilares de
monitoramento/previsão e de disseminação de alertas, com hardware e software abertos,
replicáveis e de baixo custo.

O sistema opera continuamente em campo desde dezembro de 2024 (Estação-01), com outras
duas estações instaladas ao longo de 2026, em um córrego urbano do bairro Cachoeira do Bom
Jesus, em Florianópolis (SC) — local escolhido por razões práticas de desenvolvimento, já
que construir o hardware e o firmware do zero envolveu muitos pontos de falha que exigiam
fácil acesso ao campo para depuração. Ele combina:

- **Sensoriamento in situ em tempo real** — estações ultrassônicas de nível d'água
  (Estação-01, Estação-03) e uma estação com pluviômetro de báscula (Estação-02),
  interligadas por LoRa a um gateway.
- **Fusão de dados externos** — precipitação estimada por satélite CPTEC/MERGE, usada para
  compor o histórico de treinamento anterior à Estação-02 e como alternativa em tempo real
  sempre que a Estação-02 está indisponível.
- **Previsão de nível por aprendizado de máquina** — dois modelos treinados de forma
  independente (LightGBM e Regressão Linear Múltipla) que preveem o nível d'água de 30 a 120
  minutos à frente, validados por *backtesting* contínuo sobre 21 meses de registro contra
  um catálogo de 37 episódios — 28 eventos hidrológicos confirmados e 9 excluídos por serem
  artefatos do sensor —, sob divisão cronológica treino/teste.
- **Duas camadas complementares de alerta** — um sistema de limiares sobre o nível
  observado (sem antecedência, mas sem eventos perdidos) e um sistema de previsão
  (com antecedência, controlado por um filtro de precipitação acumulada e por um filtro de
  persistência) — ambos notificam por e-mail e Telegram.
- **Um painel web** — monitoramento em tempo real e histórico, além da gestão de
  estações, contatos e alertas.

Este repositório reúne todos os componentes publicados em release e implantados na
dissertação — firmware embarcado, gateway, interface web, pipelines de dados,
treinamento/inferência dos modelos preditivos e projetos de placas (ver
[Citação](#citação) e [Como este repositório foi construído](#como-este-repositório-foi-construído)).

**Objetivos da dissertação**:

- **Geral**: desenvolver e validar um sistema de monitoramento e alerta prévio de
  inundações.
- **Específicos**: (1) implementar o monitoramento em tempo real do nível d'água e da
  precipitação; (2) aplicar um modelo de aprendizado de máquina para prever o nível de
  inundação; (3) validar o desempenho do sistema (previsão e alerta) em ambiente real.

## Sobre este projeto

- **Instituição**: Instituto Federal de Santa Catarina (IFSC) — Campus Florianópolis
- **Programa**: Mestrado em Clima e Ambiente (*Stricto Sensu*)
- **Linha de pesquisa**: Instrumentação e Desenvolvimento Tecnológico
- **Autor**: Alexandre Nuernberg
- **Situação**: dissertação em fase final de escrita; data da defesa a ser agendada

O contexto do projeto e as especificações de hardware e software estão documentados em [`docs/system-overview.md`](docs/system-overview.md) (em inglês). As mudanças
relevantes em nível de projeto estão registradas em [`CHANGELOG.md`](CHANGELOG.md).

## Visão geral do sistema

- **Estações de monitoramento** — três unidades baseadas em STM32 que transmitem por LoRa
  (915 MHz) (ver [Releases](#releases)): a Estação-01 (alimentada pela rede elétrica, nível
  d'água, ultrassônico HC-SR04, em operação desde dez/2024) e a Estação-03 (alimentada por
  energia solar, nível d'água, ultrassônico US-100, desde mar/2026) medem o nível do rio; a
  Estação-02 (alimentada por energia solar, pluviômetro de báscula, desde jan/2026) mede a
  precipitação.
- **Gateway LoRa** — receptor baseado em ESP32 (LILYGO T-SIM7000G) que autentica e decodifica
  os pacotes das estações (MessagePack + HMAC-SHA256) e os encaminha à nuvem por Wi-Fi, com
  *failover* celular NB-IoT automático.
- **Pipeline MERGE/CPTEC** — ETL horário que ingere a precipitação estimada por satélite do
  CPTEC/MERGE, usada para completar o histórico de treinamento e como alternativa em tempo
  real sempre que a Estação-02 está indisponível.
- **Interface web** — aplicação PHP/MySQL para monitoramento em tempo real, dados
  históricos, gestão de estações/contatos/alertas e um painel de previsões.
- **Modelos preditivos** — dois modelos treinados de forma independente (LightGBM e
  Regressão Linear Múltipla) que preveem o nível d'água de 30 a 120 minutos à frente.
- **Alertas automatizados** — duas camadas complementares: um sistema de limiares sobre o
  nível observado (níveis de severidade Atenção/Alerta/Inundação, imediato, sem
  antecedência) e um sistema de alerta por previsão (com antecedência, controlado por um
  filtro de precipitação acumulada e por um filtro de persistência) — ambos notificam os
  contatos cadastrados por e-mail e Telegram.

Veja o [`docs/system-overview.md`](docs/system-overview.md) para as especificações completas de hardware e software de cada
componente.

## Arquitetura

![Topologia da rede SAPI](docs/architecture/topologia-rede-sapi.png)

### Localização das estações

![Mapa de localização das estações](docs/architecture/mapa-localizacao-estacoes.png)

As Estações 01 e 03 (nível d'água) e a Estação 02 (precipitação) ficam no mesmo córrego
urbano do bairro Cachoeira do Bom Jesus, Florianópolis Norte — veja o [`docs/system-overview.md`](docs/system-overview.md) para as
coordenadas GPS exatas. Uma [versão em PDF](docs/architecture/mapa-localizacao-estacoes.pdf)
de maior resolução deste mapa também está disponível.

## Estrutura do repositório

| Caminho | Conteúdo |
|---------|----------|
| [`firmware/`](firmware/) | Estação-01, Estação-02, Estação-03 (STM32, PlatformIO) e Gateway-01 (ESP32) |
| [`hardware/`](hardware/) | Projetos KiCad 9 das duas *shields*: esquemáticos, *layouts*, *gerbers*, BOM e modelos 3D (Git LFS) |
| [`pipelines/merge2mysql/`](pipelines/merge2mysql/) | Ingestão da precipitação MERGE/CPTEC (FTP → CDO → MySQL) |
| [`webserver/`](webserver/) | Interface web PHP/MySQL, *cron jobs* de alerta, API, esquema do banco |
| [`predictive-models/`](predictive-models/) | M4 (LightGBM) e M6 (MLR): treino, inferência de produção, resultados finais do *backtest* e o PDF de auditoria |
| [`docs/`](docs/) | Visão geral do sistema, figuras de arquitetura, guias de implantação e de projeto, testes de bancada, proveniência |
| [`tools/`](tools/) | A auditoria de credenciais executada no *pre-commit* e na CI |

## Releases

Cada componente de produção recebe uma *tag* e é publicado como uma
[GitHub Release](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases),
em geral com o firmware compilado, o modelo treinado ou o arquivo-fonte anexado:

| Componente | Tag | Conteúdo |
|-----------|-----|----------|
| Estação-01 (nível d'água) | [`station-01-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-01-v1.0.0) | Firmware STM32 BluePill |
| Estação-02 (pluviômetro) | [`station-02-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-02-v1.0.0) | Firmware STM32 Nucleo F103RB |
| Estação-03 (nível d'água) | [`station-03-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-03-v1.0.0) | Firmware STM32 Nucleo L476RG |
| Gateway-01 | [`gateway-01-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/gateway-01-v2.0.0) | Firmware ESP32 — Wi-Fi principal + *failover* celular NB-IoT |
| Shield Morpho V1.2 | [`shield-morpho-v1.2.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/shield-morpho-v1.2.0) | Projeto de hardware KiCad |
| SAPI LoRa Arduino Shield V1.0 | [`shield-lora-arduino-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/shield-lora-arduino-v1.0.0) | Projeto de hardware KiCad |
| Pipeline MERGE2MySQL | [`merge2mysql-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/merge2mysql-v1.0.0) | *Scripts* de ingestão de precipitação |
| Interface web | [`webserver-v1.1.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/webserver-v1.1.0) | Código-fonte da aplicação PHP/MySQL — a versão em operação (a [`v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/webserver-v1.0.0) é a primeira release) |
| Modelo 4 (LightGBM) | [`model4-lgbm-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/model4-lgbm-v2.0.0) | Modelo treinado + arquivo de proveniência + código de treino + cópia dos dados |
| Modelo 6 (Regressão Linear Múltipla) | [`model6-mlr-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/model6-mlr-v2.0.0) | Modelo treinado + arquivo de proveniência + código de treino + cópia dos dados |

## Primeiros passos

Cada componente tem seu próprio README com detalhes de compilação, ligação e configuração:

- Estações: [`firmware/station-01/`](firmware/station-01/README.md),
  [`firmware/station-02/`](firmware/station-02/README.md),
  [`firmware/station-03/`](firmware/station-03/README.md)
- Gateway: [`firmware/gateway-01/`](firmware/gateway-01/README.md) — o binário não é
  publicado (ele embutiria as credenciais de Wi-Fi e da API); compile a partir do
  `credentials_sample.h`
- Pipeline MERGE/CPTEC: [`pipelines/merge2mysql/`](pipelines/merge2mysql/README.md)
- Interface web: [`webserver/`](webserver/README.md) (ver
  [`docs/webserver/deployment-guide.md`](docs/webserver/deployment-guide.md))
- Projetos de placas: [`hardware/`](hardware/README.md)
- Modelos preditivos (LightGBM / MLR): veja o
  [`predictive-models/README.md`](predictive-models/README.md) para os pontos de entrada de
  produção e a instalação. Os modelos de produção são treinados por
  [`train_production_from_backtest.py`](predictive-models/train_production_from_backtest.py),
  que executa o mesmo caminho de código do *backtest*, e não uma implementação separada. O
  catálogo de cheias usado no treinamento/teste é
  [`results_final_m4_lgbm/event_windows_v3.csv`](predictive-models/results_final_m4_lgbm/event_windows_v3.csv)
  — 37 episódios, 28 válidos; os gráficos-síntese de comparação M4 × M6 são
  [`compare_m4_vs_m6.png`](predictive-models/results_final_m6_mlr/output/compare_m4_vs_m6.png)
  e
  [`lead_time_comparison_m4_vs_m6.png`](predictive-models/results_final_m6_mlr/output/lead_time_comparison_m4_vs_m6.png);
  a
  [tabela de correspondência `event_detected_NNN.png` → evento catalogado](predictive-models/results_final_m4_lgbm/README.md#auto-detected-period--catalogued-event-mapping)
  está no `results_final_m4_lgbm/README.md`.

O firmware é compilado com o [PlatformIO](https://platformio.org/); a interface web requer
PHP e MySQL.

### Clonar sem os modelos 3D

Os projetos KiCad trazem ~0,9 GB de modelos 3D de terceiros em Git LFS. Se você só precisa
do código, pule-os:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/alexandreberg/SAPI_an_open_source_FEWS.git
```

Os projetos KiCad completos, com os modelos 3D, também estão anexados às releases
`shield-*` como arquivos `.tar.gz`.

## Como este repositório foi construído

O SAPI foi desenvolvido em um repositório privado, com ~520 commits de experimentos. Este
repositório público foi construído a partir dele em 24/09/2026 com **um commit por release,
em ordem cronológica**, de modo que cada *tag* aponta para uma árvore em que o seu
componente está exatamente naquela versão. As datas de autoria são as datas originais das
releases; as datas de *commit* são as da importação. O histórico de desenvolvimento continua
privado; números de issue como `#80` nas notas de release e nos documentos referem-se a ele.

Antes de cada *commit*, a árvore foi comparada arquivo a arquivo com a *tag* original
(diferenças permitidas: os cabeçalhos de licença acrescentados depois e a troca do
identificador da conta de hospedagem por `<HOSTINGER_USER>`) e auditada contra credenciais.
Os detalhes — correspondência das *tags*, o que foi alterado e o que ficou de fora — estão
em [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## Licença

<a href="LICENSE"><img alt="AGPL v3" src="docs/licensing/logos/agplv3-with-text-162x68.png" height="60"></a>
<a href="LICENSES/CERN-OHL-S-2.0.txt"><img alt="Open Source Hardware" src="docs/licensing/logos/open-source-hardware-logo.svg" height="60"></a>

Copyright (C) 2024–2026 Alexandre Nuernberg.

- **Software** (firmware, interface web, *scripts* Python) — [GNU Affero General Public
  License v3.0 ou posterior](LICENSE) (AGPL-3.0-or-later).
- **Hardware** (projetos de placas em `hardware/`) — [CERN Open Hardware Licence v2 —
  Strongly Reciprocal](LICENSES/CERN-OHL-S-2.0.txt) (CERN-OHL-S-2.0).

As dependências de terceiros estão creditadas em [`NOTICE`](NOTICE). Veja
[`docs/licensing/SAPI_Licensing_Report.md`](docs/licensing/SAPI_Licensing_Report.md)
para a justificativa completa do licenciamento e a auditoria de compatibilidade das
dependências.

## Citação

Se você usar o SAPI, seus dados ou seu código em trabalhos acadêmicos, por favor cite:

> NUERNBERG, Alexandre. *Desenvolvimento e Validação do SAPI: Um Sistema
> Integrado de Monitoramento, Alerta e Predição de Inundações*. Dissertação
> (Mestrado) — Instituto Federal de Santa Catarina (IFSC), Programa de
> Pós-Graduação em Clima e Ambiente. Florianópolis, 2026. Defesa a ser
> agendada — verifique as [Releases](#releases) deste repositório para a
> versão do código associada à versão final do trabalho.

Os metadados de citação legíveis por máquina estão em [`CITATION.cff`](CITATION.cff) (o GitHub os mostra como *Cite this repository*).

## Autor

Alexandre Nuernberg
