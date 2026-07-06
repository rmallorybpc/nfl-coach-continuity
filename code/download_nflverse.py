#!/usr/bin/env python3
"""
Download NFL production data (2013-2026) from nflverse using ONLY Python's
standard library. No pip install, no numpy, no compiler. Works on Python 3.14.

It queries GitHub for each nflverse dataset's current file list and downloads
the CSV (or parquet if no CSV) for our seasons into a folder called nflverse_raw.

RUN (VS Code terminal, Windows):
    py download_nflverse.py

Then zip the nflverse_raw folder and upload the zip (or upload the CSVs inside).

If you see a GitHub rate-limit message, wait a few minutes and run it again;
it skips files already downloaded, so rerunning is safe and resumes.
"""

import json, os, re, sys, time, urllib.request

YEARS = set(range(2013, 2027))
REPO = "nflverse/nflverse-data"
# datasets we need: offense production, rosters, snaps (availability), id crosswalk
TAGS = ["player_stats", "stats_player", "rosters", "weekly_rosters",
        "snap_counts", "players"]
HDR = {"User-Agent": "nflverse-dl", "Accept": "application/vnd.github+json"}
OUT = "nflverse_raw"


def api(url, raw=False):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=90) as r:
        b = r.read()
    return b if raw else json.loads(b)


def want(name):
    if not name.lower().endswith((".csv", ".parquet")):
        return False
    m = re.search(r"(19|20)\d\d", name)      # per-season file?
    if m:
        return int(m.group(0)) in YEARS
    return True                               # combined / all-seasons file


def main():
    os.makedirs(OUT, exist_ok=True)
    got = 0
    for tag in TAGS:
        try:
            rel = api(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
        except Exception as e:
            msg = str(e)
            if "rate limit" in msg.lower() or "403" in msg:
                print("\nGitHub rate limit hit. Wait a few minutes and rerun "
                      "(already-downloaded files are skipped).")
                break
            print(f"  tag {tag}: skipped ({type(e).__name__})")
            continue
        assets = rel.get("assets", [])
        names = {a["name"] for a in assets}
        picked = 0
        for a in assets:
            n = a["name"]
            if not want(n):
                continue
            # if a CSV twin of this parquet exists, prefer the CSV
            if n.endswith(".parquet") and (n[:-8] + ".csv") in names:
                continue
            dest = os.path.join(OUT, f"{tag}__{n}")
            if os.path.exists(dest):
                got += 1
                picked += 1
                continue
            try:
                data = api(a["browser_download_url"], raw=True)
                with open(dest, "wb") as f:
                    f.write(data)
                got += 1
                picked += 1
                print(f"  wrote {dest}  ({len(data)//1024} KB)")
                time.sleep(0.3)
            except Exception as e:
                print(f"  FAIL {n}: {type(e).__name__}")
        print(f"tag {tag}: {picked} files")
    print(f"\ndone: {got} files in {OUT}/")
    print("Zip that folder and upload the zip, or upload the CSVs inside it.")


if __name__ == "__main__":
    main()
