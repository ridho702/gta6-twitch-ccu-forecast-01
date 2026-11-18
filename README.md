# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ridho702/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ridho702/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A forecaster for Grand Theft Auto VI's launch-day Twitch audience: given
everything recorded up to the end of the release day's first hour (19 Nov
2026, UTC), it predicts the concurrent viewers in the "Grand Theft Auto VI"
Twitch category for each of hours 2–24 as five quantiles (5%, 25%, 50%, 75%,
95%). One file, `main.py` (Python 3.13, standard library only, no network,
deterministic — two runs on the same case write identical bytes, in ~0.06 s
a case).

## Run it

```sh
MAKEFUN_INPUT_DIR=<cases> MAKEFUN_OUTPUT_DIR=out python3 main.py
```

It reads every `<id>.in` in the input directory and writes `<id>.out` to the
output directory: `{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, …]}`,
23 rows, hours 2–24.

## Method: comparable-launch ratio curves

1. **Ratio curves.** Every comparable launch in the case ships its
   release-day hourly curve (SullyGnome's hourly Twitch category
   averages). For each comparable we form the ratio of each hour's viewers
   to that launch's hour-1 print, so the shape is scale-free: a launch
   ten times bigger still contributes the same shape.
2. **A pool of structurally similar launches.** We keep only comparables
   whose hour-1 print was 5%–70% of their own release-day peak. Launches
   below 5% are games whose category was nearly dead at 00:00 UTC because
   their main market unlocked much later in the day — their curves explode
   100–2000× and say nothing about a rolling-midnight launch. Launches at
   70%+ are games whose hour 1 already was their peak (simultaneous
   global unlocks). GTA VI unlocks at midnight local time, rolling by
   country — New Zealand 11:00Z on 18 Nov, central Europe 23:00Z, the UK
   00:00Z, the US east coast 05:00Z and west coast 08:00Z — so a large
   audience (UK, Europe, Oceania, Asia) is already live at hour 1 while
   the largest Twitch market (the US) still arrives in hours 6–9: hour 1
   is a minority share of the day's peak, inside [5%, 70%). In the
   practice cases this keeps 21 of 38 comparables.
3. **Empirical quantiles.** For each forecast hour, the five quantiles are
   the empirical quantiles of the log-ratios across the pooled
   comparables, scaled by the case's own hour-1 print. The 5%–95% band is
   floored at 2 × 1.645 × 0.40 log units wide, so a chance agreement among
   the comparables never yields an over-confident band.
4. **Fallback.** If no comparable survives the filter (or a pooled hour
   has fewer than 5 reporting comparables), that hour falls back to the
   house persistence baseline: every hour at the hour-1 print with a
   spread widening as 0.15 × √(h − 1).

The GTA VI category's own pre-release history ships as a comparable marked
"Not a launch" and is excluded: it has no release day, so its points must
never feed a ratio curve. The case's `streams` and `categories_hourly`
fields are unused — they are null in every practice case, so their value
cannot be validated — and the pre-release `history` baseline is unused
too: across the comparables, log(hour-1 / pre-release baseline) correlates
only −0.34 with log(peak / hour-1), too weak to condition on.

## Validation (measured, not claimed)

Scored with the contest's own rule — mean pinball loss on the log scale
over every hour and level — against the practice answers (SullyGnome's
hourly averages for the four practice launches, fetched from SullyGnome's
public chart API; hour-1 prints match the cases exactly).

| Case | This entry | House baseline | Typical miss | 90% coverage |
|---|---|---|---|---|
| Marvel's Wolverine (2026-09-15) | 0.435 | 0.744 | 111.9% | 0.96 |
| Red Dead Redemption 2 (2018-10-26) | 0.167 | 0.287 | 24.7% | 1.00 |
| God of War Ragnarök (2022-11-09) | 0.183 | 0.215 | 34.4% | 1.00 |
| Marvel's Spider-Man 2 (2023-10-20) | 0.206 | 0.303 | 32.2% | 0.96 |
| **Mean** | **0.248** | **0.387** | **50.8%** | **0.98** |

The baseline column reproduces the house's own stated practice figure
(~0.387) exactly, which validates the scorer. Leave-one-out
cross-validation over the 21 pooled comparables (each treated as a target
launch, predicted from the other 20) gives a mean loss of 0.315 against
0.402 for the baseline, at 0.85 coverage.

## Assumptions and uncertainty

The dominant uncertainty is **how steeply viewership rises after hour 1**.
Across past launches the peak/hour-1 ratio spans 1.0× (Elden Ring, whose
hour 1 already was its peak) to 9.1× (Marvel's Wolverine). The forecast's
bands encode that honestly: by hour 19 the 5%–95% band spans roughly 4–10×
from its lower to its upper end. If GTA VI's hour-1 print turns out small
relative to its peak — a US-heavy audience still to unlock — the median
will underpredict the late hours, but the 95% quantile reaches ~4× the
median there. Conversely, if hour 1 is already near the peak, the 5%
quantile sits ~40% below the median. The bands, not the medians, carry the
honest uncertainty; the pinball loss scores both on one scale.

## Sources

- Viewer counts: SullyGnome.com hourly Twitch category averages (the
  case data itself; practice answers re-fetched from SullyGnome's public
  chart API). SullyGnome publishes no open licence; the figures are
  factual counts of Twitch's public directory, quoted with attribution.
- GTA VI release: 19 November 2026 on PlayStation 5 and Xbox Series X|S,
  midnight local time rolling by country, pre-load from 10 November 2026
  (Rockstar Games / PlayStation Store listings, as reported November 2026).
- Scale benchmarks for context: the biggest single-player launch on
  Twitch was Hogwarts Legacy at 1.28M peak concurrent viewers (Guinness
  World Records, 9 Feb 2023); Elden Ring peaked at ~875k hourly average
  viewers (the kit's comparable notes); the all-time launch record is
  Valorant's closed beta at 1.74M (StreamsCharts, Nov 2026). GTA VI's
  August 2026 gameplay reveal alone drew 3.97M peak viewers across
  9,000+ channels (StreamsCharts) — the launch-day category count this
  entry forecasts is a different, narrower measure than those peaks.

---

<sub>Entered on [make.fun](https://make.fun/?ref=pxdmc197&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
