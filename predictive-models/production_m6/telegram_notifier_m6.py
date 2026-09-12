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
@file telegram_notifier_m6.py
@brief Telegram notification module for SAPI M6 MLR predictive alert transitions (Issue #120).

Sends a chart image (fired) or plain text (cleared) to all configured Telegram
chat IDs when the M6 MLR pipeline fires or clears a predictive alert.

Isolated from M4's telegram_notifier.py — labels say "M6 MLR" and the config
path points to MLR_Production/config/telegram_config.json.

Config file (JSON, chmod 600, never committed):
    /home/ilha3d/SAPI/MLR_Production/config/telegram_config.json

    {
      "bot_token": "1234567890:ABCDEFabcdef...",
      "chat_ids": ["-1001234567890", "987654321"]
    }

@author Alexandre Nuernberg
"""

import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import requests

import config_production_m6 as cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_tg_config: dict | None = None


def _load_config() -> dict | None:
    """Load Telegram bot config from the JSON file.

    @return Dict with 'bot_token' and 'chat_ids', or None if missing/malformed.
    """
    global _tg_config
    if _tg_config is not None:
        return _tg_config

    path = cfg.TELEGRAM_CONFIG_PATH
    if not os.path.isfile(path):
        logger.warning(
            "Telegram config not found: %s — Telegram notifications disabled", path
        )
        return None

    try:
        with open(path) as f:
            data = json.load(f)

        if not data.get("bot_token") or not data.get("chat_ids"):
            logger.warning("Telegram config missing 'bot_token' or 'chat_ids'")
            return None

        _tg_config = data
        logger.info("Telegram config loaded (%d chat ID(s))", len(data["chat_ids"]))
        return _tg_config

    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load Telegram config: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

_THRESH_STYLE: dict[str, tuple[str, str]] = {
    "atencao":   ("#f5c518", "Atenção"),
    "alerta":    ("#fd7e14", "Alerta"),
    "inundacao": ("#dc3545", "Inundação"),
}

_ALERT_PT: dict[str, str] = {
    "atencao":   "ATENÇÃO",
    "alerta":    "ALERTA",
    "inundacao": "INUNDAÇÃO",
    "none":      "Normalizado",
}


def build_alert_chart(
    result: dict,
    level_rows: list[dict],
    station_id: int,
) -> bytes:
    """Render a prediction snapshot chart for a fired M6 MLR alert.

    @param result      Enriched prediction result dict.
    @param level_rows  Raw API rows for the station's level history.
    @param station_id  Station identifier.
    @return PNG image as bytes.
    """
    ts_now = datetime.now(timezone.utc)

    raw_times = [pd.Timestamp(r["timestamp"], tz="UTC") for r in level_rows]
    raw_vals  = [
        float(r["value"]) if r["value"] is not None else float("nan")
        for r in level_rows
    ]
    ser = pd.Series(raw_vals, index=raw_times, dtype=float).sort_index()
    cutoff = ts_now - timedelta(hours=2)
    ser = ser[ser.index >= cutoff]

    horizons   = [30, 60, 90, 120]
    pred_keys  = {30: "h_pred_30", 60: "h_pred_60", 90: "h_pred_90", 120: "h_pred_120"}
    pred_times = [ts_now + timedelta(minutes=h) for h in horizons]
    pred_vals  = [float(result[pred_keys[h]]) for h in horizons]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#ffffff")

    if not ser.empty:
        ax.plot(
            ser.index, ser.values,
            color="#1565C0", linewidth=2,
            label="Nível medido (cm)", zorder=3,
        )
        ax.plot(
            [ser.index[-1], pred_times[0]],
            [ser.iloc[-1],  pred_vals[0]],
            color="#E65100", linewidth=1.5, linestyle="--", alpha=0.5, zorder=2,
        )

    # Deep orange dashed line — matches the M6 colour in predictions.php
    ax.plot(
        pred_times, pred_vals,
        color="#E65100", linewidth=2, linestyle="--",
        marker="o", markersize=8,
        label="Previsão M6 MLR (cm)", zorder=4,
    )

    for t, v, h in zip(pred_times, pred_vals, horizons):
        ax.annotate(
            f"+{h}min\n{v:.0f} cm",
            xy=(t, v),
            xytext=(0, 14), textcoords="offset points",
            ha="center", fontsize=8, color="#E65100",
            zorder=5,
        )

    thresh = cfg.THRESHOLDS.get(station_id, {})
    for key, (color, label) in _THRESH_STYLE.items():
        val = thresh.get(key)
        if val is not None:
            ax.axhline(val, color=color, linewidth=1.5, linestyle=":",
                       alpha=0.9, label=f"{label}: {val} cm", zorder=1)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 15, 30, 45]))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    alert_label = _ALERT_PT.get(result.get("alert_level", "none"), "?")
    ts_str      = ts_now.strftime("%Y-%m-%d %H:%M UTC")
    ax.set_title(
        f"Alerta Preditivo M6 MLR — Estação {station_id} — {alert_label} — {ts_str}",
        fontsize=12, fontweight="bold", pad=10,
    )
    ax.set_xlabel("Horário (UTC)", fontsize=10)
    ax.set_ylabel("Nível (cm)", fontsize=10)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.85)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

_TG_TIMEOUT = 30


def _tg_url(bot_token: str, method: str) -> str:
    """Build a Telegram Bot API endpoint URL.

    @param bot_token  BotFather-issued token.
    @param method     Telegram method name.
    @return Full URL string.
    """
    return f"https://api.telegram.org/bot{bot_token}/{method}"


def send_telegram_photo(
    bot_token: str,
    chat_id: str,
    caption: str,
    img_bytes: bytes,
) -> bool:
    """Upload and send a PNG image to a Telegram chat.

    @param bot_token  BotFather token.
    @param chat_id    Recipient chat or group ID.
    @param caption    Text shown below the photo (max 1024 chars).
    @param img_bytes  PNG image as bytes.
    @return True on success, False on any error.
    """
    url = _tg_url(bot_token, "sendPhoto")
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("alert.png", img_bytes, "image/png")},
            timeout=_TG_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("ok"):
            return True
        logger.warning("sendPhoto: Telegram error: %s", body.get("description"))
        return False
    except Exception as exc:
        logger.warning("sendPhoto failed (chat_id=%s): %s", chat_id, exc)
        return False


def send_telegram_text(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a plain text message to a Telegram chat.

    @param bot_token  BotFather token.
    @param chat_id    Recipient chat or group ID.
    @param message    Message text (max 4096 chars).
    @return True on success, False on any error.
    """
    url = _tg_url(bot_token, "sendMessage")
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": message},
            timeout=_TG_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("ok"):
            return True
        logger.warning("sendMessage: Telegram error: %s", body.get("description"))
        return False
    except Exception as exc:
        logger.warning("sendMessage failed (chat_id=%s): %s", chat_id, exc)
        return False


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def _build_fired_caption(result: dict, station_id: int) -> str:
    """Build the image caption for a fired M6 alert notification.

    @param result      Enriched prediction result dict.
    @param station_id  Station identifier.
    @return Caption string (<=1024 chars for Telegram sendPhoto).
    """
    alert_label = _ALERT_PT.get(result.get("alert_level", "none"), "?")
    ts_str      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"[SAPI] Alerta Preditivo M6 MLR — {alert_label}",
        f"Estação {station_id} | {ts_str}",
        "",
        "Projeções de nível:",
        f"  +30 min : {result['h_pred_30']:.1f} cm",
        f"  +60 min : {result['h_pred_60']:.1f} cm",
        f"  +90 min : {result['h_pred_90']:.1f} cm",
        f" +120 min : {result['h_pred_120']:.1f} cm",
        "",
        f"Precipitação (6h): {result['precip_rolling']:.1f} mm ({result['precip_source']})",
        f"Passos debounce  : {result.get('consecutive_steps', '?')} / {cfg.DEBOUNCE_STEPS}",
    ]
    return "\n".join(lines)


def _build_cleared_message(result: dict, station_id: int) -> str:
    """Build the text message for a cleared M6 alert notification.

    @param result      Enriched prediction result dict.
    @param station_id  Station identifier.
    @return Message string.
    """
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"[SAPI] Alerta Preditivo M6 MLR Normalizado — Estação {station_id}",
        f"Timestamp: {ts_str}",
        "",
        "Situação normalizada — todos os horizontes abaixo dos limites.",
        "",
        "Projeções atuais:",
        f"  +30 min : {result['h_pred_30']:.1f} cm",
        f"  +60 min : {result['h_pred_60']:.1f} cm",
        f"  +90 min : {result['h_pred_90']:.1f} cm",
        f" +120 min : {result['h_pred_120']:.1f} cm",
        "",
        f"Precipitação (6h): {result['precip_rolling']:.1f} mm ({result['precip_source']})",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def notify_alert(
    result: dict,
    level_rows: list[dict],
    station_id: int,
    fired: bool,
    cleared: bool,
) -> bytes | None:
    """Send Telegram notifications for an M6 MLR predictive alert transition.

    @param result      Enriched prediction result dict.
    @param level_rows  Raw level API rows for chart rendering.
    @param station_id  Station identifier.
    @param fired       True when alert transitions from none to active.
    @param cleared     True when alert transitions from active to none.
    @return PNG chart bytes on fired (or None on failure), None on cleared.
    """
    if not fired and not cleared:
        return None

    tg = _load_config()
    if tg is None:
        return None

    bot_token = tg["bot_token"]
    chat_ids  = tg["chat_ids"]

    if fired:
        try:
            img_bytes = build_alert_chart(result, level_rows, station_id)
        except Exception as exc:
            logger.error("build_alert_chart failed: %s — falling back to text", exc)
            img_bytes = None

        caption = _build_fired_caption(result, station_id)
        for chat_id in chat_ids:
            if img_bytes:
                ok = send_telegram_photo(bot_token, chat_id, caption, img_bytes)
            else:
                ok = send_telegram_text(bot_token, chat_id, caption)
            logger.info("Telegram fired → chat_id=%s ok=%s", chat_id, ok)

        return img_bytes

    elif cleared:
        message = _build_cleared_message(result, station_id)
        for chat_id in chat_ids:
            ok = send_telegram_text(bot_token, chat_id, message)
            logger.info("Telegram cleared → chat_id=%s ok=%s", chat_id, ok)
        return None
