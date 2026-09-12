# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
@file 05_event_catalogue.py
@brief Visual catalogue of the catalogued hydrological events (Issue #138).

Event count, train/test split, thresholds and the period are all derived from
config.EVENTS_CSV and config.THRESHOLD_*, so this figure cannot drift away from
the catalogue again (it used to hardcode the v2 catalogue and 50/60/75 cm).

Produces a single wide-format timeline of the full 16-month observation period
(Dec/2024 – May/2026) with:
  - Observed level (h_obs) from the M4 continuous backtesting run
  - Shaded event windows: orange = training events, blue = test events
  - Peak markers annotated with E-number and peak_cm
  - Horizontal alert threshold lines (from config.THRESHOLD_*)

This plot is intended for the dissertation methodology section to illustrate
the event catalogue and train/test split strategy.

Input files:
  results_final_m4_lgbm/output/continuous_predictions.csv  (h_obs column)
  results_final_m4_lgbm/event_windows_v3.csv (via config.EVENTS_CSV)

Output:
  results_final_m4_lgbm/output/event_catalogue.png

Usage (run from the results_final_m4_lgbm/ folder):

    cd AppTest/raspberry/predictive_model_darts/results_final_m4_lgbm/
    python3 05_event_catalogue.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import config

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions.csv")
EVENTS_CSV = config.EVENTS_CSV
"""Event catalogue — follows config so the figure never lags the catalogue
(the v2 path used to be hardcoded here, which kept this dissertation figure on
the superseded 20-event catalogue and the old 50/60/75 thresholds)."""
OUTPUT_PNG = os.path.join(config.OUTPUT_DIR, "event_catalogue.png")

MESES = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]
"""Portuguese month abbreviations: strftime's %b follows the C locale and would
print English names ("dec/2024 - sep/2026") on this dissertation figure."""

COLOR_TRAIN = "#E65100"  # deep orange for training events
COLOR_TEST = "#1565C0"  # dark blue for test events
COLOR_LEVEL = "#546E7A"  # blue-grey for the observed level line
COLOR_ATENCAO = "#F9A825"  # amber
COLOR_ALERTA = "#E65100"  # orange
COLOR_INUNDACAO = "#B71C1C"  # dark red

ALPHA_SHADE = 0.20
ALPHA_SHADE_TRAIN = 0.28

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Load data and produce the event catalogue plot."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 66)
    print("  Event Catalogue (Issue #138)")
    print("=" * 66)

    # ── 1. Load data ─────────────────────────────────────────────────────────
    print(f"\n[1/2] Loading:\n  {PREDS_CSV}")
    if not os.path.exists(PREDS_CSV):
        print(
            "  [ERROR] continuous_predictions.csv not found.\n"
            "         Run 01_model4_continuous.py first."
        )
        sys.exit(1)
    df = pd.read_csv(
        PREDS_CSV, parse_dates=["timestamp"], usecols=["timestamp", "h_obs"]
    )
    df = df.dropna(subset=["h_obs"]).sort_values("timestamp").reset_index(drop=True)
    print(
        f"  Loaded {len(df):,} rows  "
        f"({df['timestamp'].min()} → {df['timestamp'].max()})"
    )

    print(f"\n[2/2] Loading:\n  {EVENTS_CSV}")
    df_ev = pd.read_csv(
        EVENTS_CSV,
        parse_dates=["peak_time", "analysis_start", "analysis_end"],
    )
    print(
        f"  Loaded {len(df_ev)} events "
        f"({(df_ev['split_set']=='train').sum()} train, "
        f"{(df_ev['split_set']=='test').sum()} test)."
    )

    # ── 2. Build figure ───────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 5))

    # Observed level line
    ax.plot(
        df["timestamp"],
        df["h_obs"],
        color=COLOR_LEVEL,
        linewidth=0.6,
        alpha=0.85,
        zorder=2,
        label="Cota observada (cm)",
    )

    # Sensor artifacts (Issue #227) are not hydrological events — they are kept
    # in the catalogue for auditing but must not appear in this figure.
    if "exclusion" in df_ev.columns or (df_ev["split_set"] == "excluded").any():
        n_excluded = int((df_ev["split_set"] == "excluded").sum())
        df_ev = df_ev[df_ev["split_set"] != "excluded"].copy()
    else:
        n_excluded = 0
    n_train = int((df_ev["split_set"] == "train").sum())
    n_test = int((df_ev["split_set"] == "test").sum())

    # Shaded event windows
    legend_train_added = False
    legend_test_added = False
    for _, row in df_ev.iterrows():
        is_train = row["split_set"] == "train"
        color = COLOR_TRAIN if is_train else COLOR_TEST
        alpha = ALPHA_SHADE_TRAIN if is_train else ALPHA_SHADE
        label = None
        if is_train and not legend_train_added:
            label = f"Treino ({n_train} eventos)"
            legend_train_added = True
        elif not is_train and not legend_test_added:
            label = f"Teste ({n_test} eventos)"
            legend_test_added = True
        ax.axvspan(
            row["analysis_start"],
            row["analysis_end"],
            color=color,
            alpha=alpha,
            zorder=1,
            label=label,
        )

    # Peak annotations — alternate label height to avoid overlap
    for i, (_, row) in enumerate(df_ev.iterrows()):
        event_num = int(row["event_num"])
        peak_cm = float(row["peak_cm"])
        t_peak = row["peak_time"]
        color = COLOR_TRAIN if row["split_set"] == "train" else COLOR_TEST

        # Stagger label y between two levels to prevent label pile-up
        y_label = peak_cm + (8 if i % 2 == 0 else 16)
        ax.annotate(
            f"E{event_num:02d}\n{peak_cm:.0f} cm",
            xy=(t_peak, peak_cm),
            xytext=(t_peak, y_label),
            fontsize=6.5,
            color=color,
            ha="center",
            va="bottom",
            fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.6),
            zorder=4,
        )
        ax.plot(t_peak, peak_cm, "v", color=color, markersize=4, zorder=3)

    # Alert threshold lines
    thresholds = [
        (
            config.THRESHOLD_ATENCAO,
            COLOR_ATENCAO,
            f"Atenção ({config.THRESHOLD_ATENCAO:.0f} cm)",
        ),
        (
            config.THRESHOLD_ALERTA,
            COLOR_ALERTA,
            f"Alerta ({config.THRESHOLD_ALERTA:.0f} cm)",
        ),
        (
            config.THRESHOLD_INUNDACAO,
            COLOR_INUNDACAO,
            f"Inundação ({config.THRESHOLD_INUNDACAO:.0f} cm)",
        ),
    ]
    for h, color, label in thresholds:
        ax.axhline(
            h,
            color=color,
            linewidth=1.0,
            linestyle="--",
            alpha=0.75,
            zorder=2,
            label=label,
        )

    # Axes formatting
    ax.set_xlim(df["timestamp"].min(), df["timestamp"].max())
    ax.set_ylim(20, df["h_obs"].max() + 30)
    ax.set_ylabel("Cota (cm)", fontsize=10)
    ax.set_xlabel("")

    def _mes_ano(ts):
        """Format a timestamp as Portuguese "mmm/aaaa"."""
        return f"{MESES[ts.month - 1]}/{ts.year}"

    periodo = f"{_mes_ano(df['timestamp'].min())} – {_mes_ano(df['timestamp'].max())}"
    subtitulo = f"{n_train + n_test} eventos válidos: {n_train} treino + {n_test} teste"
    if n_excluded:
        subtitulo += f"  ({n_excluded} artefatos de sensor excluídos)"
    ax.set_title(
        f"Catálogo de Eventos Hidrológicos — Estação-01 ({periodo})\n" + subtitulo,
        fontsize=11,
    )

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _pos: (
                f"{MESES[mdates.num2date(x).month - 1]}\n{mdates.num2date(x).year}"
            )
        )
    )
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator())
    ax.tick_params(axis="x", which="major", labelsize=8)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    ax.grid(axis="x", which="major", alpha=0.15)

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles,
        labels,
        loc="upper left",
        fontsize=8,
        ncol=3,
        framealpha=0.85,
        edgecolor="grey",
    )

    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=150)
    plt.close(fig)
    print(f"\n  Saved {OUTPUT_PNG}")
    print("=== EVENT CATALOGUE DONE ===\n")


if __name__ == "__main__":
    main()
