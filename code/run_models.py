#!/usr/bin/env python3
"""
run_models.py
Run every regression in the reunion-premium study from the assembled frame,
with the study populations made explicit:
  - production / availability: signings with a measurable prior role
  - pay premium: real-market contracts only (AAV > $2M)

    python run_models.py --frame data/production_retention_frame.csv
"""
import argparse
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

POOL = ["QB","RB","WR","TE","DL","LB","DB"]

def fit(df, formula, key):
    m = smf.ols(formula, data=df).fit()
    ci = m.conf_int().loc[key]
    return m.params[key], m.pvalues[key], int(m.nobs), (ci[0], ci[1])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--frame", default="data/production_retention_frame.csv")
    F = pd.read_csv(ap.parse_args().frame)
    print(f"resolvable signings: {len(F)}")
    print(f"reunions  head coach {int(F.R_hc.sum())}  coordinator {int(F.R_coord.sum())}  position coach {int(F.R_full.sum())}")
    print(f"with a measurable prior role: {int(F.has_prior_role.sum())}   real-market contracts: {int(F.market.sum())}\n")

    # 1. pay premium — market contracts only
    d = F[F.market == 1].dropna(subset=["log_aav"])
    b, p, n, ci = fit(d, "log_aav ~ R_full + C(position_group) + C(sign_year) + C(to_team)", "R_full")
    print("PAY PREMIUM  (market contracts, AAV > $2M)")
    print(f"  {np.exp(b)-1:+.1%}  (p={p:.2f}, 95% CI {np.exp(ci[0])-1:+.1%} to {np.exp(ci[1])-1:+.1%}, n={n}, reunions={int(d.R_full.sum())})\n")

    # 2. production retention — players with a prior role
    print("PRODUCTION RETENTION  (prior-role players; pooled offense + defense)")
    pooled = F[F.position_group.isin(POOL)]
    print(f"  {'definition':16}{'1-season':30}{'2-season':30}")
    for rf, lab in [("R_hc","head coach"),("R_coord","coordinator"),("R_full","position coach")]:
        cells = []
        for dv in ["out_prod_1yr","out_prod_2yr"]:
            dd = pooled.dropna(subset=[dv,"base_prod","age"])
            b,p,n,_ = fit(dd, f"{dv} ~ {rf} + base_prod + age + C(position_group) + C(sign_year)", rf)
            cells.append(f"{b:+.3f} (p={p:.2f}, n={n})")
        print(f"  {lab:16}{cells[0]:30}{cells[1]:30}")

    # 3. availability
    print("\nAVAILABILITY")
    for lab, df in [("all prior-role", F), ("market only", F[F.market == 1])]:
        dd = df.dropna(subset=["out_avail","base_avail","age"])
        b,p,n,_ = fit(dd, "out_avail ~ R_full + base_avail + age + C(position_group) + C(sign_year)", "R_full")
        print(f"  {lab:16}{b:+.3f} (p={p:.2f}, n={n})")

if __name__ == "__main__":
    main()
