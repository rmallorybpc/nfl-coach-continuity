#!/usr/bin/env python3
"""
build_events.py  (corrected treatment, v3)

Reunion is an EVENT, not a signing: a player and a coach are on the same team now,
were not both on it the prior year (one of them arrived), and were together at an
earlier team where that coach actually covered the player's position group.

Two types:
  player_move  - the player arrived at the coach's team
  coach_move   - the coach arrived at the player's team

This replaces the signing-based definition, which counted same-team re-signings as
reunions and produced a spurious result. Builds a player-season panel.

    python build_events.py --nflverse-dir nflverse_raw --staff data/coaching_staff_2013_2026.xlsx --out data/reunion_panel.csv
"""
import argparse, glob, sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_reunions as B

ALL={'QB','RB','WR','TE','OL','DL','LB','DB','ST'}; OFFG={'QB','RB','WR','TE','OL'}; DEFG={'DL','LB','DB'}
COLG={'QB Coach':{'QB'},'RB Coach':{'RB'},'WR Coach':{'WR'},'TE Coach':{'TE'},'OL Coach':{'OL'},
      'DL Coach':{'DL'},'LB Coach':{'LB'},'DB/Secondary Coach':{'DB'},'Special Teams Coach':{'ST'}}
POOL=['QB','RB','WR','TE','DL','LB','DB']

def load_rosters(nfv):
    tt={}; pos={}; g2pfr={}; age={}
    for f in sorted(glob.glob(f"{nfv}/rosters__roster_20*.csv")):
        d=pd.read_csv(f,usecols=lambda c:c in ('season','team','position','birth_date','gsis_id','pfr_id'))
        for r in d.itertuples():
            g=getattr(r,'gsis_id',None); c=B.fixcode(getattr(r,'team',None))
            if not (isinstance(g,str) and g and c): continue
            tt.setdefault(g,{}).setdefault(r.season,set()).add(c); pos[(g,r.season)]=B.pgroup(getattr(r,'position',None))
            pid=getattr(r,'pfr_id',None); bd=getattr(r,'birth_date',None)
            if isinstance(pid,str): g2pfr[g]=pid
            if isinstance(bd,str) and len(bd)>=4:
                try: age[(g,r.season)]=r.season-int(bd[:4])
                except ValueError: pass
    return tt,pos,g2pfr,age

def load_avail(nfv):
    sn=pd.concat([pd.read_csv(f,usecols=['season','pfr_player_id','position','offense_pct','defense_pct','st_pct'])
                  for f in sorted(glob.glob(f"{nfv}/snap_counts__snap_counts_20*.csv"))])
    sn['snap']=sn[['offense_pct','defense_pct','st_pct']].max(axis=1)
    sa=sn.groupby(['season','pfr_player_id','position'],as_index=False)['snap'].mean(); sa['pg']=sa['position'].map(B.pgroup)
    sa['apct']=sa.groupby(['pg','season'])['snap'].rank(pct=True)
    return {(r.pfr_player_id,r.season):r.apct for r in sa.itertuples()}

def coach_coverage(staff):
    hcocdc,pos_staff,_=staff; cover={}; coach_ty={}
    def add(nm,s,t,grps):
        if nm: cover.setdefault((nm,s,t),set()).update(grps); coach_ty.setdefault(nm,set()).add((s,t))
    for (s,t),d in hcocdc.items(): add(d.get('HC'),s,t,ALL); add(d.get('OC'),s,t,OFFG); add(d.get('DC'),s,t,DEFG)
    for (s,t),cd in pos_staff.items():
        for col,nm in cd.items(): add(nm,s,t,COLG.get(col,set()))
    return cover,coach_ty

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--nflverse-dir",default="nflverse_raw"); ap.add_argument("--staff",default="data/coaching_staff_2013_2026.xlsx")
    ap.add_argument("--out",default="data/reunion_panel.csv"); ap.add_argument("--start",type=int,default=2015); ap.add_argument("--end",type=int,default=2024)
    a=ap.parse_args()
    tt,pos,g2pfr,age=load_rosters(a.nflverse_dir); av=load_avail(a.nflverse_dir)
    prod=B.production_by_gsis(a.nflverse_dir); staff=B.load_staff(a.staff); _,_,staff_all=staff
    cover,coach_ty=coach_coverage(staff)
    def coached_before(g,nm,Y):
        for y,teams in tt.get(g,{}).items():
            if y<Y and any(pos.get((g,y)) in cover.get((nm,y,A),set()) for A in teams): return True
        return False
    etype={}
    for g,seasons in tt.items():
        for Y,teams in seasons.items():
            if not(a.start<=Y<=a.end) or len(teams)!=1: continue
            T=next(iter(teams)); pgp=pos.get((g,Y))
            for nm in staff_all.get((Y,T),set()):
                if pgp not in cover.get((nm,Y,T),set()) or not coached_before(g,nm,Y): continue
                if (T in tt.get(g,{}).get(Y-1,set())) and ((Y-1,T) in coach_ty.get(nm,set())): continue
                etype[(g,Y)]='player_move' if T not in tt.get(g,{}).get(Y-1,set()) else ('coach_move' if (Y-1,T) not in coach_ty.get(nm,set()) else 'other')
                break
    rows=[]
    for g,seasons in tt.items():
        for Y,teams in seasons.items():
            if not(a.start<=Y<=a.end) or len(teams)!=1: continue
            o=prod.get((g,Y)); b=prod.get((g,Y-1)); ag=age.get((g,Y)); pg=pos.get((g,Y))
            if o is None or b is None or ag is None or pg not in POOL: continue
            t=etype.get((g,Y),'none'); pfr=g2pfr.get(g); prev=tt.get(g,{}).get(Y-1,set())
            rows.append(dict(gsis=g,season=Y,pg=pg,base=b,out=o,age=ag,
                reunion=int(t in('player_move','coach_move')),player_move=int(t=='player_move'),coach_move=int(t=='coach_move'),
                moved=int(next(iter(teams)) not in prev and len(prev)>0),
                base_av=av.get((pfr,Y-1)),out_av=av.get((pfr,Y))))
    P=pd.DataFrame(rows); os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True); P.to_csv(a.out,index=False)
    print(f"wrote {a.out}: {len(P)} player-seasons | player_move {int(P.player_move.sum())} | coach_move {int(P.coach_move.sum())}")

if __name__=="__main__": main()
