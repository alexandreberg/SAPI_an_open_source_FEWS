# MERGE2MySQL Code

## This repo contains code to convert the MERGE data, usually in **grib2** format, to **CSV** files and then uploads the *precipitation* data to a **MySQL** server in the Cloud.

The **MERGE directory**, hosted on the **CPTEC/INPE FTP server**, contains meteorological data, primarily related to **Satellite Estimated Precipitation products**. The term "MERGE" likely refers to a *data fusion product* that combines information from various *remote sensing sources*—such as the **GOES** and **GPM** satellite missions (as suggested by the subdirectories)—to create a *highly detailed* and more **accurate precipitation field**. This type of high-resolution data is essential for **real-time rainfall monitoring**, improving weather forecasting models, hydrological studies, and climate research conducted by the Brazilian Center for Weather Forecasting and Climate Studies.

* **CPTEC**: Centro de Previsão de Tempo e Estudos Climáticos (Center for Weather Forecasting and Climate Studies).
* **INPE**: Instituto Nacional de Pesquisas Espaciais (National Institute for Space Research).

### MERGE repo: <https://ftp.cptec.inpe.br/modelos/tempo/MERGE/>

---

## Main codes

The project is composed of these codes:

* `merge_crontab_wrapper.sh`
* `0-sincroniza_repo_merge_crontab.sh`
* `2-processa_dia_completo_crontab.sh`

### merge\_crontab\_wrapper.sh

Is a **wrapper** that runs in the **crontab**, syncing the MERGE repo **every hour**.

```bash
$ crontab -l
0 * * * * /dados/Pessoal/Mestrado/MERGE/merge_crontab_wrapper.sh
```

### 0-sincroniza_repo_merge_crontab.sh

This code called by `merge_crontab_wrapper.sh` does the synchronization of the <https://ftp.cptec.inpe.br/modelos/tempo/MERGE/GPM/HOURLY/2025/> locally for processing (This can be changed for any desired MERGE folder).

### 2-processa_dia_completo.sh

This is the **main processing script** that performs the actual GRIB2 to CSV conversion. It:
1. Converts GRIB2 files to NetCDF format using CDO
2. Extracts precipitation data for a specified latitude/longitude point (ROI)
3. Generates CSV files with hourly precipitation data

### 2-processa_dia_completo_crontab.sh

This is the **crontab orchestrator** that calls `2-processa_dia_completo.sh` for each day that needs processing. It handles:
- Tracking which days have been processed
- Incremental processing (only new/incomplete days)
- Logging and error handling

### 3-importar_dados_crontab.sh

This code imports the CSV data to MySQL database. it does partially checking the start date and hour in the file: 
```bash
$ cat ultima_importacao.log
2025-11-23 19:00
```
And just import data after this date and time.

## Aditional script files:
### 3-importar_dados_lote.sh
It is used to do the importing via comand line trough this menu:
```bash
 ./3-importar_dados_lote.sh
========================================
   Importação em Lote - MERGE → MySQL
========================================

Escolha o tipo de importação:
1) Arquivo único (diário)
2) Mês completo
3) Ano completo

Opção [1-3]:
```
The options are:
* 1) `import just a single CSV file`
* 2) `import a full month`
* 3) `import a full year`

---

## Platform Compatibility (ARM64 / x86_64)

This code has been tested and runs on both **x86_64** (Ubuntu/Dell G3) and **ARM64** (Raspberry Pi 4) platforms.

### CDO Version Differences

The Climate Data Operators (CDO) tool is used for GRIB2 to NetCDF conversion and data extraction. Different CDO versions use different variable names for the precipitation data:

| Platform | CDO Version | Precipitation Variable Name |
|----------|-------------|----------------------------|
| x86_64 (Ubuntu) | 2.4.0 | `prec` |
| ARM64 (Raspberry Pi) | 2.5.1 | `rdp` |

Both refer to the same GRIB2 parameter (`5.15.0` - Precipitation from radar), but the naming convention changed between CDO versions.

### The Fix

The `2-processa_dia_completo.sh` script includes **dynamic variable detection** to work on both platforms:

```bash
# Detect precipitation variable name (prec in CDO 2.4.x, rdp in CDO 2.5.x)
VAR_NAME=$(cdo showname "$NC_FILE" 2>/dev/null | tr ' ' '\n' | grep -E '^(prec|rdp)$' | head -1)
```

This ensures compatibility across different CDO versions and architectures.

### Minor Value Differences

Due to floating-point arithmetic differences between x86_64 and ARM64 architectures, there may be **minor differences** (~0.01mm) in extracted precipitation values when processing the same GRIB2 file on different platforms. These differences are negligible for practical purposes.

### CPTEC Data Updates

CPTEC may update their GRIB2 files over time with corrected/improved data. If you notice **significant differences** in precipitation values between systems, it's likely due to downloading the GRIB2 files at different times. The most recently downloaded data should be considered the most accurate.

### Verifying GRIB2 File Integrity

To verify if GRIB2 files are identical between two systems, generate MD5 checksums:

```bash
# On each system
cd /path/to/MERGE/GPM/HOURLY/2026
find . -name "*.grib2" -type f | sort | xargs md5sum > md5_checksums.log
```

Then compare the logs to identify files with different content.

---