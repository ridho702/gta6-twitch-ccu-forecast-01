"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Entry for make.fun's gta6-twitch-ccu-forecast-01 bounty (program/v1).

The program reads one case file per run (/input/<id>.in, schema
"makefun/twitch-ccu-case/v1") and writes /output/<id>.out: for each of hours
2..24 of the release day (UTC), five quantiles (5%, 25%, 50%, 75%, 95%) of
that hour's concurrent Twitch viewers in the game's category.

Method: comparable-launch ratio curves (see README.md for the full write-up).

  1. Every comparable launch in the case ships its release-day hourly curve
     (SullyGnome's hourly Twitch category averages). For each comparable we
     form the ratio of each hour's viewers to that launch's hour-1 print.
  2. We keep only the comparables whose hour-1 print was a plausible share
     of their own release-day peak (5% to 70%). Launches below 5% are games
     whose category was nearly dead at 00:00 UTC because their main market
     unlocked much later in the day (their curves explode 100-2000x and
     say nothing about a rolling-midnight launch like GTA VI); launches
     at 70%+ are games whose hour 1 already was their peak (simultaneous
     global unlocks the day before in UTC terms). GTA VI unlocks at
     midnight local time, rolling by country -- New Zealand 11:00Z on
     18 Nov, central Europe 23:00Z, the UK 00:00Z, the US east coast
     05:00Z and west coast 08:00Z -- so a large audience is already live
     at hour 1 and the largest market (the US) still arrives in hours
     6-9: hour 1 is a minority share of the day's peak, inside [5%, 70%).
  3. For each forecast hour, the forecast quantiles are the empirical
     quantiles of the log-ratios across the kept comparables, scaled by
     the case's own hour-1 print. The spread is floored at a log-sigma of
     0.40 (the 5%-95% band is at least 2 x 1.645 x 0.40 log units wide),
     so the bands stay honest where the comparables happen to agree.
  4. If no comparable survives the filter (or the case carries none), the
     program falls back to the house persistence baseline: every hour at
     the hour-1 print with a spread widening as 0.15 x sqrt(h - 1).

The program is deterministic (no randomness, no wall-clock use, no
network): two runs on the same case write identical bytes. Standard
library only; runs in well under the 8-second cap (the case files are
~1 MB and the work is a few thousand arithmetic operations).

Usage:
    MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import sys
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# Quantile levels the contest scores, in the order each output row lists.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at those levels (used only by the fallback).
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Comparable filter: keep a launch only when its hour-1 print was between
# these shares of its own release-day peak. See the module docstring.
POOL_LOW = 0.05
POOL_HIGH = 0.70
# Minimum log-sigma of the forecast spread (the 5%-95% band is at least
# 2 * 1.645 * SPREAD_FLOOR log units wide).
SPREAD_FLOOR = 0.40
# Fallback (house persistence baseline) spread per square-root hour.
BASELINE_SIGMA = 0.15
# Smallest viewer count a quantile may take (quantiles must be above 0).
Q_MIN = 0.01
# Largest viewer count a quantile may take (the contest caps at 1e9).
Q_MAX = 1_000_000_000.0


def round2(x: float) -> float | int:
    """Round to 2 decimals, half up (the starter's rounding convention)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str):
    """Parse an ISO 8601 UTC timestamp into a datetime."""
    from datetime import datetime

    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_curve(comparable: dict) -> dict[int, float]:
    """A comparable's release-day hourly viewers, keyed by hour 1..24.

    Hours are counted from the comparable's day_start (00:00 UTC of its
    release date). Points outside the release day are ignored, as are
    missing (None) points: SullyGnome samples small categories sparsely.
    """
    day_start = parse_time(comparable["day_start"])
    curve: dict[int, float] = {}
    for point in comparable.get("hourly", []):
        viewers = point.get("viewers")
        if viewers is None:
            continue
        hour = int((parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            curve[hour] = float(viewers)
    return curve


def percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile of an already sorted list."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = p * (n - 1)
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def hour_quantiles(p1: float, log_ratios: list[float], levels: list[float]) -> list[float | int]:
    """Quantiles of an hour's viewers from the log-ratios of its comparables.

    The median is the median log-ratio; the other quantiles are the matching
    empirical percentiles. The 5%-95% band is widened to at least
    2 * 1.645 * SPREAD_FLOOR log units, so a chance agreement among the
    comparables never yields an over-confident band.
    """
    ordered = sorted(log_ratios)
    quantiles = [percentile(ordered, tau) for tau in levels]
    if len(levels) >= 2:
        low_i, high_i = 0, len(levels) - 1
        width = quantiles[high_i] - quantiles[low_i]
        # The outer levels sit 1.645 normal sigmas from the median on each
        # side, so the band is at least 2 * 1.645 * SPREAD_FLOOR log units
        # wide; widen it symmetrically around its centre when it is not.
        needed = 2 * 1.645 * SPREAD_FLOOR
        if width < needed:
            centre = (quantiles[low_i] + quantiles[high_i]) / 2
            quantiles[low_i] = centre - needed / 2
            quantiles[high_i] = centre + needed / 2
    values = [p1 * math.exp(q) for q in quantiles]
    values = [min(max(v, Q_MIN), Q_MAX) for v in values]
    # Keep the row non-decreasing (the widening above can only move the
    # outer quantiles outward, but stay safe after clamping).
    for i in range(1, len(values)):
        values[i] = max(values[i], values[i - 1])
    return [round2(v) for v in values]


def baseline_quantiles(p1: float, hour: int) -> list[float | int]:
    """House persistence baseline: every hour at the hour-1 print."""
    return [round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1))) for z in Z]


def hour1_print(case: dict) -> float:
    """The case's hour-1 print, with defensive fallbacks (never crashes)."""
    for row in case.get("known", []):
        if row.get("hour") == 1 and row.get("viewers") is not None:
            return max(1.0, float(row["viewers"]))
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if last is not None:
            return max(1.0, float(last))
    return 1.0


def forecast_case(case: dict, name: str) -> dict:
    """Forecast hours 2..24 of one case as five quantiles each."""
    p1 = hour1_print(case)
    levels = case.get("levels") or LEVELS

    # Build the pool of structurally similar comparables.
    curves: list[dict[int, float]] = []
    for comparable in case.get("comparables", []):
        # The GTA VI category's own pre-release history ships as a
        # comparable marked "Not a launch": it has no release day, so its
        # hourly points must never feed a ratio curve.
        if str(comparable.get("unlock", "")).startswith("Not a launch"):
            continue
        curve = release_day_curve(comparable)
        if 1 not in curve or curve[1] <= 0:
            continue
        peak = max(curve.values())
        if peak <= 0:
            continue
        if POOL_LOW <= curve[1] / peak < POOL_HIGH:
            curves.append(curve)

    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        if curves:
            log_ratios = [
                math.log(curve[hour] / curve[1])
                for curve in curves
                if hour in curve and curve[hour] > 0
            ]
        else:
            log_ratios = []
        if len(log_ratios) >= 5:
            quantiles = hour_quantiles(p1, log_ratios, levels)
        else:
            # Too few comparables report this hour: fall back to the
            # persistence baseline for the hour rather than guessing.
            quantiles = baseline_quantiles(p1, hour)
        rows.append({"hour": hour, "q": quantiles})
    return {"hours": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
