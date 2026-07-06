#!/usr/bin/env python3
"""
add_av_outcome.py
Fold Pro Football Reference Approximate Value (AV) into the analysis frame as a
second, all-position production outcome. AV is the only public number that covers
offensive linemen, so this is what lifts the study off its skill-position sample.

AV is not scrapeable within PFR's terms. Export it from Stathead instead:
  Stathead > Football > Season Finder > Player Season Finder
  filter to the seasons you need (e.g. 2013-2026), add the Approximate Value (AV)
  column, and export to CSV. One export covering all seasons is enough.

The script auto-detects the common Stathead column names. It needs, per row, a
player name, a season, a team, a position, and AV. A PFR player id column is used
if present (most reliable).

    python add_av_outcome.py \
        --frame data/production_retention_frame.csv \
        --av-export stathead_av.csv \
        --nflverse-dir nflverse_raw \
        --out data/production_retention_frame_av.csv

Then run the models with AV outcomes:
    python run_models.py --frame data/production_retention_frame_av.csv --av
"""

import argparse, re, sys, os
import numpy as np, pandas as pd
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import build_reunions as B   # reuse clean, fixcode, pgroup, N2C, build_crosswalk

# PFR / Stathead team codes -> dataset codes (on top of build_reunions.CODEFIX)
PFR = {"CRD":"ARI","RAV":"BAL","HTX":"HOU","CLT":"IND","OTI":"TEN","SDG":"LAC",
       "RAM":"LAR","RAI":"LV","NWE":"NE","NOR":"NO","GNB":"GB","SFO":"SF",
       "TAM":"TB","KAN":"KC"}
def teamcode(t):
    c = B.fixcode(t)
    return PFR.get(str(t).strip().upper(), c)

def pick(cols, *cands):
    low = {c.lower(): c for c in cols}
    for x in cands:
        if x in low: return low[x]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default="data/production_retention_frame.csv")
    ap.add_argument("--av-export", required=True)
    ap.add_argument("--nflverse-dir", default="nflverse_raw")
    ap.add_argument("--out", default="data/production_retention_frame_av.csv")
    a = ap.parse_args()

    av = pd.read_csv(a.av_export)
    c_name = pick(av.columns, "player", "name")
    c_year = pick(av.columns, "season", "year", "yr")
    c_team = pick(av.columns, "team", "tm")
    c_pos  = pick(av.columns, "pos", "position")
    c_av   = pick(av.columns, "av", "approx_value", "approximate_value")
    c_pfr  = pick(av.columns, "pfr_id", "player_id", "player-additional", "-9999")
    missing = [n for n,c in {"name":c_name,"season":c_year,"team":c_team,"pos":c_pos,"AV":c_av}.items() if c is None]
    if missing:
        sys.exit(f"AV export is missing columns for: {', '.join(missing)}. Columns present: {list(av.columns)}")

    av = av.rename(columns={c_name:"name",c_year:"season",c_team:"team",c_pos:"pos",c_av:"AV"})
    av = av[pd.to_numeric(av["season"], errors="coerce").notna()].copy()
    av["season"] = av["season"].astype(int)
    av["AV"] = pd.to_numeric(av["AV"], errors="coerce")
    av = av.dropna(subset=["AV"])
    av["pname"] = av["name"].map(B.clean)
    av["code"]  = av["team"].map(teamcode)
    av["pg"]    = av["pos"].map(B.pgroup)

    # within-position-season percentile of AV (cross-position comparable, like the primary outcome)
    av["av_pct"] = av.groupby(["pg","season"])["AV"].rank(pct=True)

    # resolve each AV row to a gsis id
    ctx,ns,allname,gpos,gseas,pfr2gsis,hist,age = B.build_crosswalk(a.nflverse_dir)
    def to_gsis(r):
        if c_pfr and isinstance(r.get(c_pfr), str) and r[c_pfr] in pfr2gsis:
            return pfr2gsis[r[c_pfr]]
        g = ctx.get((r["pname"], r["season"], r["code"]))
        if g: return g
        s = ns.get((r["pname"], r["season"]))
        if s and len(s) == 1: return next(iter(s))
        cand = allname.get(r["pname"], set())
        return next(iter(cand)) if len(cand) == 1 else None
    av["gsis"] = av.apply(lambda r: to_gsis(r if c_pfr is None else {**r, c_pfr: r.get(c_pfr)}), axis=1)
    av = av.dropna(subset=["gsis"])
    avmap = {(g, s): p for g, s, p in zip(av["gsis"], av["season"], av["av_pct"])}

    F = pd.read_csv(a.frame)
    def look(g, y): return avmap.get((g, y))
    F["base_av"]      = [look(g, y-1) for g, y in zip(F["gsis"], F["sign_year"])]
    F["out_av_1yr"]   = [look(g, y)   for g, y in zip(F["gsis"], F["sign_year"])]
    F["out_av_2yr"]   = [np.nanmean([v for v in (look(g, y), look(g, y+1)) if v is not None]) if any(look(g, y+k) is not None for k in (0,1)) else np.nan
                         for g, y in zip(F["gsis"], F["sign_year"])]
    F.to_csv(a.out, index=False)

    have = F.dropna(subset=["base_av","out_av_2yr"])
    ol = F[F.position_group == "OL"].dropna(subset=["base_av","out_av_2yr"])
    print(f"wrote {a.out}")
    print(f"AV outcome present for {len(have)} signings (was ~{int(F['out_prod_2yr'].notna().sum())} on box-score production)")
    print(f"offensive line now modelable: {len(ol)} of {(F.position_group=='OL').sum()}")

if __name__ == "__main__":
    main()
