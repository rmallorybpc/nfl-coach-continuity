# Audit log — the reunion premium

A record of data decisions, corrections, and how the result changed as the data
was cleaned. Kept so the research is reproducible and its history is legible.

## Data assembly and corrections

**Coaching staffs, 2013–2026.** Head coach through position coach, all 32 teams.
Coordinators supplied by the study; position coaches scraped from
pro-football-history.com. 448 team-seasons; position coaches populated for
2013–2025 (2026 not yet published by the source; one 2025 team-season missing).

**Coach corrections (4), each a same-season duplicate resolved to the correct team:**

| Season | Team | Role | Was | Corrected to | Reason |
|---|---|---|---|---|---|
| 2013 | NY Jets | DC | Mike Pettine | Dennis Thurman | Pettine moved to Buffalo in 2013 |
| 2015 | Cleveland | OC | Kyle Shanahan | John DeFilippo | Shanahan was Atlanta's OC in 2015 |
| 2017 | NY Giants | DC | James Bettcher | Steve Spagnuolo | Bettcher was Arizona's DC through 2017 |
| 2025 | Washington | DC | Dennard Wilson | Joe Whitt Jr. | Wilson is Tennessee's DC |

**Player identity.** Resolved to nflverse gsis id via name + season + team context.
92% of signings resolved. This replaced name-only matching, which collided on 163
shared names (multiple A.J. Greens and the like) and leaked false reunions.

**Prior-team history.** Union of nflverse rosters (2013–2026) and nfldata rosters
(2006–2019), joined by id, spanning 2006–2026.

**Production.** nflverse seasonal stats, 2013–2024, expressed as a within-position
percentile. The defensive metric was changed from a hand-weighted score to an
equal-weight standardized z-average after the hand weights were found to drive a
result (see below).

**Populations fixed explicitly.** Production and availability on players with a
measurable prior role; the pay premium on real-market contracts (AAV > $2M).

## How the result changed

The result moved three times as the data improved. Recorded in full, because the
movement is the point.

1. **First pass (Approximate Value, 2017–2019, 11 reunions).** A small positive
   hint, not significant. Underpowered, and AV is team-contaminated.
2. **Name-matched percentile pipeline.** Production −0.05 to −0.07, borderline.
   Reported at the time as near-null after a defensive-metric cleanup. Pay premium
   reported as +14% (p = 0.016).
3. **Consolidation into a committed pipeline** exposed three problems: the +14%
   premium was an artifact of the minimum-salary tier (on market contracts it was
   ~0–3% and never significant); player identity was name-based and collided; and
   only ~15% of resolvable signings had a measurable post-move season.
4. **Identity-resolved, corrected-staff pipeline (current).** Pay premium +0.9%
   (p = 0.88, none). Production −0.06 (p = 0.03 pooled), consistent across head
   coach, coordinator, and position coach and across one- and two-season windows.
   Availability roughly flat.

**Why it moved.** Name-collision noise averaged the real signal toward zero. Clean
identity resolution and the staff corrections tightened the estimate, and a small,
consistent negative emerged. The premium never survived restriction to real
contracts, in any version.

## Robustness of the current result

- **Selection.** Reunion and non-reunion players have identical baseline production
  (0.443 vs 0.443) and near-identical age (29.4 vs 29.1). The negative is not
  mean-reversion or aging.
- **Nonlinearity.** Survives squared baseline and age terms (−0.057, p = 0.04).
- **Placebo.** Shuffling the reunion label 200 times centers on zero; the real
  −0.062 lies outside the entire placebo distribution.
- **Fragility.** The effect is small (~6 percentile points) and fades to
  non-significance on market-only or single-side subsamples. It needs the pooled
  sample of ~73 reunions to detect.

## Standing decisions

- No number reaches the site unless `run_models.py` produced it from the committed
  `production_retention_frame.csv`.
- One history source, one staff file, one frame. No inline one-off analyses feed
  published figures.

*The Mallory Group — 2026.*

## Scope note: the offensive line

Offensive-line production quality is not part of this study, because it is not
publicly measurable. Box scores carry no line production stat, and Approximate
Value, the only number that covers the line, is unavailable for recent seasons
without a paid Sports Reference / Stathead subscription. A free partial check
using AV for 2006-2019 overlapped only the 2017-2019 signings (103 players, 9
reunions) and was too thin to use. For the line the study therefore relies on
availability, whether the player held his snaps and starts. The AV join
(`code/add_av_outcome.py`) is written and ready should a Stathead export ever be
obtained, at which point the line becomes measurable and the sample roughly
triples.
