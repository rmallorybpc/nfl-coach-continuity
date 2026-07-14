#!/usr/bin/env python3
"""
run_events.py  — corrected reunion models from the player-season panel.
Each reunion type is compared to its fair control: movers to movers, stayers to stayers.

    python run_events.py --panel data/reunion_panel.csv
"""
import argparse
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

def fit(df,key,dv="out",base="base"):
    d=df.dropna(subset=[dv,base,"age"])
    m=smf.ols(f"{dv} ~ {key} + {base} + age + C(pg) + C(season)",data=d).fit()
    ci=m.conf_int().loc[key]
    return m.params[key],m.pvalues[key],int(m.nobs),int(d[key].sum()),(ci[0],ci[1])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--panel",default="data/reunion_panel.csv")
    P=pd.read_csv(ap.parse_args().panel)
    print(f"player-seasons: {len(P)} | player-move reunions: {int(P.player_move.sum())} | coach-move reunions: {int(P.coach_move.sum())}\n")
    print("PRODUCTION RETENTION  (within-position percentile; controls: prior season, age, position, year)")
    for sub,key,lab in [(P[P.moved==1],"player_move","player-move vs other movers"),
                        (P[P.moved==0],"coach_move","coach-move vs other stayers")]:
        b,p,n,t,ci=fit(sub,key)
        print(f"  {lab:32} {b:+.3f}  (p={p:.2f}, 95% CI {ci[0]:+.3f} to {ci[1]:+.3f}, n={n}, reunions={t})")
    print("\nAVAILABILITY  (snap-share percentile)")
    for sub,key,lab in [(P[P.moved==1],"player_move","player-move vs other movers"),
                        (P[P.moved==0],"coach_move","coach-move vs other stayers")]:
        b,p,n,t,ci=fit(sub,key,dv="out_av",base="base_av")
        print(f"  {lab:32} {b:+.3f}  (p={p:.2f}, n={n}, reunions={t})")
    print("\nPLACEBO  (shuffle treatment within control, 200x)")
    rng=np.random.default_rng(1)
    for sub,key,lab in [(P[P.moved==1].dropna(subset=['out','base','age']),"player_move","player-move"),
                        (P[P.moved==0].dropna(subset=['out','base','age']),"coach_move","coach-move")]:
        real=smf.ols(f"out ~ {key} + base + age + C(pg) + C(season)",data=sub).fit().params[key]
        ph=[smf.ols("out ~ f + base + age + C(pg) + C(season)",data=sub.assign(f=rng.permutation(sub[key].values))).fit().params['f'] for _ in range(200)]
        ph=np.array(ph)
        print(f"  {lab:12} real {real:+.3f} | placebo 95% [{np.percentile(ph,2.5):+.3f},{np.percentile(ph,97.5):+.3f}] | as-extreme {100*np.mean(np.abs(ph)>=abs(real)):.0f}%")

if __name__=="__main__": main()
