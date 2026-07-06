# nfl-coach-continuity

**The reunion premium.** Do NFL free agents who sign with a team where a coach
already knows them retain more production than comparable players who do not?
This repository holds the data, code, and site for that study.

Site: https://rmallorybpc.github.io/nfl-coach-continuity/

## Findings

On identity-matched data, across free-agent signings from 2017 to 2026, using
within-position production percentiles with controls for prior baseline, age,
position, and year:

- **No pay premium.** On real-market contracts (AAV > $2M), reunion signings are
  paid -0.8% relative to comparable signings (p = 0.90). Nothing. An earlier +14%
  figure was an artifact of the minimum-salary tier.
- **A small negative on production.** Reunited players retain about 0.06 percentile
  points *less*, not more (pooled p = 0.03), consistent across head coach,
  coordinator, and position coach and across one- and two-season windows. It
  survives selection, nonlinearity, and placebo checks. It is small and fades on
  subsamples, so it rests on the pooled sample of ~73 reunions.
- **Availability roughly flat** (−0.02, p = 0.31).

The headline: teams pay no premium to reunite a player with a former coach, and
reunited players retain slightly less production, not more. The market's core
belief points the wrong way. The effect is small and the sample is modest, so it
is stated with care. See `docs/audit-log.md` for how the result changed as the
data was cleaned.

Treatment size: 524 cross-team reunions among 3,917 resolvable signings
(92% of players id-resolved); the production model rests on 430 prior-role
players with 74 reunions.

## Repository structure

```
nfl-coach-continuity/
├── index.html  findings.html  methods.html  audit.html  data.html   GitHub Pages site
├── study.css                                             site supplement (TMG tokens)
├── TMG-BRAND-GUIDE.md                                    design source of truth
├── data/
│   ├── coaching_staff_2013_2026.xlsx    assembled staffs, HC through position coach
│   ├── production_retention_frame.csv   per-signing analysis frame (committed)
│   └── cross_team_reunions.csv          the reunion list
├── code/
│   ├── scrape_position_coaches.py       builds the staff table
│   ├── download_nflverse.py             pulls production, rosters, snaps (run local)
│   ├── build_reunions.py                source data -> analysis frame
│   ├── add_av_outcome.py                folds in PFR Approximate Value (all positions)
│   └── run_models.py                    frame -> all regressions
├── docs/audit-log.md                    decision + correction record
└── .gitignore                           excludes nflverse_raw/
```

The site links the shared TMG stylesheet over CDN, so `tmg.css` is not copied here.

## Reproduce

```bash
# 1. production data (large; not committed). run where the network is open.
python code/download_nflverse.py                       # -> nflverse_raw/

# 2. build the analysis frame from staffs + signings + production
python code/build_reunions.py \
    --staff data/coaching_staff_2013_2026.xlsx \
    --movement /path/to/movement_events.csv \
    --nflverse-dir nflverse_raw \
    --extra-rosters /path/to/nfldata_rosters.csv        # optional, deepens history

# 3. run every model reported on the site
python code/run_models.py --frame data/production_retention_frame.csv

# optional: add all-position Approximate Value coverage (needs a Stathead export)
python code/add_av_outcome.py --frame data/production_retention_frame.csv \
    --av-export stathead_av.csv --nflverse-dir nflverse_raw
python code/run_models.py --frame data/production_retention_frame_av.csv --av
```

`data/production_retention_frame.csv` is committed, so step 3 runs on its own
without re-downloading anything.

## Data sources

- Signings and contracts: open free-agency movement dataset (Spotrac-sourced).
- Production and availability: nflverse seasonal stats and snap counts.
- Prior-team history: nflverse rosters, optionally deepened with nfldata rosters.
- Coaching staffs: assembled 2013 to 2026 from public listings. Ships here.

## Caveats

Reunion cells are modest (roughly 250 to 580 depending on the cut), so a null is
a failure to find the paid-for effect, not proof of a true zero. Production is
cleanest for skill offense and noisy for the line and much of defense; linemen
are measured on availability alone. The whole study is observational: a
backward-looking measurement, not a signing tool.

*The Mallory Group — 2026.*
