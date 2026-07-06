#!/usr/bin/env python3
"""
build_reunions.py  (v2 — identity-resolved)

Assemble the per-signing analysis frame for the reunion-premium study, joining
players by stable id (gsis / pfr) resolved from name + season + team context,
rather than by name alone. This removes name-collision leakage.

Reads:  coaching staff workbook; free-agency movement dataset; nflverse seasonal
        offense + defense stats, snap counts, rosters; optional deep-history
        roster file keyed by pfr id (nfldata rosters).
Writes: production_retention_frame.csv (one row per resolvable signing, with
        population flags resolved / has_prior_role / market) and cross_team_reunions.csv

    python build_reunions.py --staff data/coaching_staff_2013_2026.xlsx \
        --movement path/to/movement_events.csv --nflverse-dir nflverse_raw \
        --extra-rosters path/to/nfldata_rosters.csv
"""

import argparse, glob, os, re
import numpy as np, pandas as pd

MARKET_AAV = 2_000_000

def clean(s):
    if s is None or (isinstance(s, float) and pd.isna(s)): return None
    s = str(s).lower(); s = re.sub(r"[.'`]", "", s); s = re.sub(r"[^a-z ]", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip() or None
def normteam(s): return re.sub(r"\s+", " ", str(s).lower().replace(".", "").replace("-", " ")).strip()
def _s(p): return "" if (p is None or (isinstance(p, float) and pd.isna(p))) else str(p).lower()
CODEFIX = {"OAK":"LV","SD":"LAC","SDG":"LAC","STL":"LAR","LA":"LAR","JAC":"JAX","ARZ":"ARI","CLV":"CLE","HTX":"HOU","NWE":"NE","NOR":"NO","TAM":"TB","KAN":"KC","GNB":"GB","SFO":"SF","RAI":"LV","RAM":"LAR"}
def fixcode(c):
    if pd.isna(c): return None
    c = str(c).strip().strip('"').upper(); return CODEFIX.get(c, c)
N2C = {"arizona cardinals":"ARI","atlanta falcons":"ATL","baltimore ravens":"BAL","buffalo bills":"BUF","carolina panthers":"CAR","chicago bears":"CHI","cincinnati bengals":"CIN","cleveland browns":"CLE","dallas cowboys":"DAL","denver broncos":"DEN","detroit lions":"DET","green bay packers":"GB","houston texans":"HOU","indianapolis colts":"IND","jacksonville jaguars":"JAX","kansas city chiefs":"KC","los angeles chargers":"LAC","san diego chargers":"LAC","los angeles rams":"LAR","st louis rams":"LAR","miami dolphins":"MIA","minnesota vikings":"MIN","new england patriots":"NE","new orleans saints":"NO","new york giants":"NYG","new york jets":"NYJ","las vegas raiders":"LV","oakland raiders":"LV","philadelphia eagles":"PHI","pittsburgh steelers":"PIT","seattle seahawks":"SEA","san francisco 49ers":"SF","tampa bay buccaneers":"TB","tennessee titans":"TEN","washington commanders":"WAS","washington football team":"WAS","washington redskins":"WAS"}
def pgroup(p):
    p=_s(p)
    for g,ss in {"QB":{"qb"},"RB":{"rb","fb","hb"},"WR":{"wr"},"TE":{"te"},"OL":{"ol","ot","og","c","g","t","lt","rt","lg","rg","iol"},"DL":{"dl","de","dt","nt","ed","edge"},"LB":{"lb","ilb","olb","mlb"},"DB":{"cb","s","fs","ss","db","saf","nb"},"ST":{"k","p","ls"}}.items():
        if p in ss: return g
    return "OTH"
OFF={"qb","rb","fb","hb","wr","te","ol","ot","og","c","g","t","lt","rt","lg","rg","iol"}
DEF={"dl","de","dt","nt","ed","edge","lb","ilb","olb","mlb","cb","s","fs","ss","db","saf","nb"}
def side_of(p):
    p=_s(p); return "OFF" if p in OFF else "DEF" if p in DEF else ("ST" if p in {"k","p","ls"} else None)
UNIT={"QB":"QB Coach","RB":"RB Coach","WR":"WR Coach","TE":"TE Coach","OL":"OL Coach","DL":"DL Coach","LB":"LB Coach","DB":"DB/Secondary Coach","ST":"Special Teams Coach"}
POSCOLS=["QB Coach","RB Coach","WR Coach","TE Coach","OL Coach","DL Coach","LB Coach","DB/Secondary Coach","Special Teams Coach"]
def parse_pid(p):
    p=str(p)
    if p.startswith("name:"):
        x=p.split(":"); return (clean(x[1].replace("-"," ")) if len(x)>1 else None),(x[2].lower() if len(x)>2 and x[2] else None)
    if p.startswith("nfl:"): return clean(p.replace("nfl:","").replace("-"," ")),None
    return clean(p),None

def load_staff(path):
    ct=pd.read_excel(path,sheet_name="NFL Coaching Staff 2013-2026",header=2)
    ct=ct[pd.to_numeric(ct["Season"],errors="coerce").notna()].copy(); ct["Season"]=ct["Season"].astype(int)
    ct["code"]=ct["Team"].map(lambda t:N2C.get(normteam(t)))
    hcocdc,pos_staff,staff_all={},{},{}
    for _,r in ct.iterrows():
        k=(r["Season"],r["code"])
        hcocdc[k]={"HC":clean(r["Head Coach"]),"OC":clean(r["Offensive Coordinator"]),"DC":clean(r["Defensive Coordinator"])}
        pos_staff[k]={c:clean(r.get(c)) for c in POSCOLS if c in ct.columns}
        staff_all[k]={v for v in hcocdc[k].values() if v}|{v for v in pos_staff[k].values() if v}
    return hcocdc,pos_staff,staff_all

def build_crosswalk(nfv):
    """Identity crosswalk + prior-team history + age, keyed by gsis.
    Indexes full, football/common, and first+last names, and records each
    player's positions and seasons so ambiguous names can be disambiguated."""
    ctx,ns,allname,gpos,gseas,pfr2gsis,hist,age={},{},{},{},{},{},{},{}
    def _add(nm,yr,code,g,pg):
        nm=clean(nm)
        if not nm or pd.isna(g) or not g: return
        if code: ctx[(nm,yr,code)]=g; ns.setdefault((nm,yr),set()).add(g)
        allname.setdefault(nm,set()).add(g)
        if pg: gpos.setdefault(g,set()).add(pg)
        gseas.setdefault(g,set()).add(yr)
    for f in sorted(glob.glob(f"{nfv}/rosters__roster_20*.csv")):
        d=pd.read_csv(f,usecols=lambda c:c in ("season","team","full_name","football_name","first_name","last_name","position","birth_date","gsis_id","pfr_id"))
        for r in d.itertuples():
            g=getattr(r,"gsis_id",None)
            if pd.isna(g) or not g: continue
            code=fixcode(getattr(r,"team",None)); pg=pgroup(getattr(r,"position",None)); yr=r.season
            for nm in (getattr(r,"full_name",None),getattr(r,"football_name",None)):
                _add(nm,yr,code,g,pg)
            fn,ln=getattr(r,"first_name",None),getattr(r,"last_name",None)
            if isinstance(fn,str) and isinstance(ln,str): _add(f"{fn} {ln}",yr,code,g,pg)
            if code: hist.setdefault(g,set()).add((yr,code))
            pid=getattr(r,"pfr_id",None)
            if isinstance(pid,str) and pid: pfr2gsis[pid]=g
            bd=getattr(r,"birth_date",None)
            if isinstance(bd,str) and len(bd)>=4:
                try: age[(g,yr)]=yr-int(bd[:4])
                except ValueError: pass
    reg=os.path.join(nfv,"players__players.csv")
    if os.path.exists(reg):
        pl=pd.read_csv(reg)
        if "gsis_id" in pl.columns:
            for r in pl.itertuples():
                g=getattr(r,"gsis_id",None)
                for c in ("display_name","football_name","full_name","short_name"):
                    nm=getattr(r,c,None) if c in pl.columns else None
                    if isinstance(nm,str) and g: allname.setdefault(clean(nm),set()).add(g)
    return ctx,ns,allname,gpos,gseas,pfr2gsis,hist,age

def add_deep_history(hist,pfr2gsis,path):
    if not path or not os.path.exists(path): return
    d=pd.read_csv(path)
    for r in d.itertuples():
        g=pfr2gsis.get(getattr(r,"playerid",None)); code=fixcode(getattr(r,"team",None))
        if g and code: hist.setdefault(g,set()).add((r.season,code))

def production_by_gsis(nfv):
    off=pd.concat([pd.read_csv(f,usecols=["season","player_id","position_group","games","fantasy_points_ppr"])
                   for f in sorted(glob.glob(f"{nfv}/player_stats__player_stats_season_20*.csv"))])
    off=off[off["games"]>=4].copy(); off["metric"]=off["fantasy_points_ppr"]
    de=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{nfv}/player_stats__player_stats_def_season_20*.csv"))])
    de=de[de["games"]>=4].copy()
    dc=["def_tackles","def_sacks","def_tackles_for_loss","def_qb_hits","def_interceptions","def_pass_defended","def_fumbles_forced"]
    for c in dc:
        de[c]=de[c].fillna(0)
        de[c+"_z"]=de.groupby(["position_group","season"])[c].transform(lambda x:(x-x.mean())/(x.std() if x.std() else 1))
    de["metric"]=de[[c+"_z" for c in dc]].mean(axis=1)
    prod=pd.concat([off[["season","player_id","position_group","metric"]],de[["season","player_id","position_group","metric"]]])
    prod["pct"]=prod.groupby(["position_group","season"])["metric"].rank(pct=True)
    return {(r.player_id,r.season):r.pct for r in prod.itertuples()}

def avail_by_pfr(nfv):
    sn=pd.concat([pd.read_csv(f,usecols=["season","pfr_player_id","position","offense_pct","defense_pct","st_pct"])
                  for f in sorted(glob.glob(f"{nfv}/snap_counts__snap_counts_20*.csv"))])
    sn["snap"]=sn[["offense_pct","defense_pct","st_pct"]].max(axis=1)
    sa=sn.groupby(["season","pfr_player_id","position"],as_index=False)["snap"].mean()
    sa["pg"]=sa["position"].map(pgroup); sa["apct"]=sa.groupby(["pg","season"])["snap"].rank(pct=True)
    return {(r.pfr_player_id,r.season):r.apct for r in sa.itertuples()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--staff",default="data/coaching_staff_2013_2026.xlsx")
    ap.add_argument("--movement",required=True)
    ap.add_argument("--nflverse-dir",default="nflverse_raw")
    ap.add_argument("--extra-rosters",default=None)
    ap.add_argument("--out-frame",default="data/production_retention_frame.csv")
    ap.add_argument("--out-reunions",default="data/cross_team_reunions.csv")
    a=ap.parse_args()

    hcocdc,pos_staff,staff_all=load_staff(a.staff)
    ctx,ns,allname,gpos,gseas,pfr2gsis,hist,age=build_crosswalk(a.nflverse_dir)
    add_deep_history(hist,pfr2gsis,a.extra_rosters)
    prod=production_by_gsis(a.nflverse_dir); avail=avail_by_pfr(a.nflverse_dir)
    gsis2pfr={g:p for p,g in pfr2gsis.items()}

    def resolve(nm,Y,to_code,from_code,pg):
        if (nm,Y,to_code) in ctx: return ctx[(nm,Y,to_code)]
        if from_code and (nm,Y-1,from_code) in ctx: return ctx[(nm,Y-1,from_code)]
        for yy in (Y,Y-1,Y+1):
            s=ns.get((nm,yy))
            if s and len(s)==1: return next(iter(s))
        cand=allname.get(nm,set())
        if len(cand)==1: return next(iter(cand))
        if len(cand)>1:
            filt=[g for g in cand if pg in gpos.get(g,set()) and any(Y-3<=s<=Y+1 for s in gseas.get(g,set()))]
            if len(filt)==1: return filt[0]
        return None

    mv=pd.read_csv(a.movement)
    fa=mv[mv["move_type"]=="free_agency"].copy()
    pp=fa["player_id"].map(parse_pid); fa["pname"]=pp.map(lambda x:x[0]); fa["pos"]=pp.map(lambda x:x[1])
    fa["to_code"]=fa["to_team_id"].map(fixcode); fa["from_code"]=fa["from_team_id"].map(fixcode); fa["Y"]=fa["nfl_season"].astype(int)
    fa=fa.sort_values("contract_aav",ascending=False).drop_duplicates(["pname","Y","to_code"])

    rows,reun,total,res=[],[],0,0
    for _,r in fa.iterrows():
        pn,Y,T,pos=r["pname"],r["Y"],r["to_code"],r["pos"]
        if not (2017<=Y<=2026): continue
        total+=1
        g=resolve(pn,Y,T,r["from_code"],pgroup(pos)); res+=(g is not None)
        cur=hcocdc.get((Y,T))
        cross=[(s,c) for (s,c) in hist.get(g,set()) if s<Y and c!=T] if g else []
        if not (g and cur is not None and cross): continue   # resolvable only
        side=side_of(pos); pf=set()
        for (s,c) in cross: pf|=staff_all.get((s,c),set())
        hc=[cur["HC"]]; coord=hc+([cur["OC"]] if side=="OFF" else [])+([cur["DC"]] if side=="DEF" else [])
        uc=UNIT.get(pgroup(pos)); cp=pos_staff.get((Y,T),{}); full=coord+([cp[uc]] if uc and cp.get(uc) else [])
        R_hc=int(any(nm and nm in pf for nm in hc)); R_coord=int(any(nm and nm in pf for nm in coord)); R_full=int(any(nm and nm in pf for nm in full))
        pfr=gsis2pfr.get(g); o1=prod.get((g,Y)); o2=prod.get((g,Y+1)); outs=[x for x in [o1,o2] if x is not None]
        aav=r.get("contract_aav")
        rows.append(dict(player=pn,gsis=g,sign_year=Y,position_group=pgroup(pos),side=side,to_team=T,
            R_hc=R_hc,R_coord=R_coord,R_full=R_full,base_prod=prod.get((g,Y-1)),out_prod_1yr=o1,
            out_prod_2yr=(np.mean(outs) if outs else None),base_avail=avail.get((pfr,Y-1)),
            out_avail=avail.get((pfr,Y)),age=age.get((g,Y)),contract_aav=aav,
            log_aav=(np.log(aav) if aav and aav>0 else None),
            market=int(bool(aav and aav>MARKET_AAV)),has_prior_role=int(prod.get((g,Y-1)) is not None)))
        if R_full:
            reun.append(dict(player=pn.title(),sign_year=Y,side=side,to_team=T,
                             via_head_coach=R_hc,via_coordinator=R_coord,via_position_coach=R_full))
    frame=pd.DataFrame(rows)
    os.makedirs(os.path.dirname(a.out_frame) or ".",exist_ok=True)
    frame.to_csv(a.out_frame,index=False)
    pd.DataFrame(reun).sort_values(["sign_year","to_team"]).to_csv(a.out_reunions,index=False)
    print(f"signings 2017-2026: {total} | id-resolved: {res} ({res/total:.0%}) | resolvable: {len(frame)}")
    print(f"reunions  head coach {int(frame.R_hc.sum())}  coordinator {int(frame.R_coord.sum())}  position coach {int(frame.R_full.sum())}")
    print(f"wrote {a.out_frame} and {a.out_reunions}")

if __name__=="__main__":
    main()
