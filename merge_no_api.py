
#!/usr/bin/env python3
"""
merge_no_api.py
----------------
Merge Salesforce Opportunities with Tubular *CSV export* (no API required).

Inputs:
  --opps opps.csv             # Salesforce export (must include Account.Name; optional channel_id field)
  --metrics tubular.csv       # Tubular CSV export with channel_id + metrics columns
  --map channel_map.csv       # OPTIONAL: map Account.Name -> channel_id if opps has no channel_id
  --out merged.csv            # Output file

Expected columns:
  opps.csv:
    - Always: Account.Name
    - Optional (better): Account.YouTube_Channel_ID__c or channel_id
  channel_map.csv:
    - account_name, channel_id
  tubular.csv:
    - channel_id, views_30d, audience_size, category, growth_30d_pct, channel_name
      (Rename columns in your CSV to these headers or use --metrics-cols to map.)

Usage:
  python merge_no_api.py --opps opps.csv --metrics tubular.csv --out merged.csv
  python merge_no_api.py --opps opps.csv --map channel_map.csv --metrics tubular.csv --out merged.csv

Advanced:
  If your Tubular CSV uses different headers, provide a mapping like:
    --metrics-cols channel_id:Channel ID,views_30d:Views (30d),audience_size:Subscribers
"""
import argparse
import pandas as pd

def parse_colmap(arg: str):
    mapping = {}
    if not arg:
        return mapping
    pairs = [p.strip() for p in arg.split(",") if p.strip()]
    for pair in pairs:
        if ":" not in pair:
            raise SystemExit(f"Bad --metrics-cols pair: {pair}. Use old:new")
        new, old = pair.split(":", 1)
        mapping[new.strip()] = old.strip()
    return mapping

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opps", required=True)
    ap.add_argument("--metrics", required=True, help="Tubular CSV export")
    ap.add_argument("--map", required=False, help="Optional channel_map.csv to attach channel_id by Account.Name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--metrics-cols", required=False, default="", help="Header mapping new:old,new:old ...")
    args = ap.parse_args()

    opps = pd.read_csv(args.opps)

    # 1) Ensure we have a channel_id column in opps, else join from map
    channel_col = None
    for col in ["Account.YouTube_Channel_ID__c", "YouTube_Channel_ID__c", "channel_id", "Channel_ID__c"]:
        if col in opps.columns:
            channel_col = col
            break

    if channel_col is None:
        if not args.map:
            raise SystemExit("Opps CSV has no channel_id column. Provide --map channel_map.csv (account_name,channel_id).")
        cmap = pd.read_csv(args.map)
        if "account_name" not in cmap.columns or "channel_id" not in cmap.columns:
            raise SystemExit("channel_map.csv must include: account_name, channel_id")
        acct_col = None
        for col in ["Account.Name", "account_name", "Account"]:
            if col in opps.columns:
                acct_col = col
                break
        if acct_col is None:
            raise SystemExit("Couldn't find Account.Name column in opps to join with channel_map.")
        opps = opps.merge(cmap[["account_name","channel_id"]], left_on=acct_col, right_on="account_name", how="left")
        channel_col = "channel_id"

    # 2) Load Tubular metrics and normalize headers
    met = pd.read_csv(args.metrics)
    colmap = parse_colmap(args.metrics_cols)

    # Apply column renames from mapping (old -> new names we expect)
    if colmap:
        met = met.rename(columns={v: k for k, v in colmap.items()})

    # Ensure required columns exist in metrics CSV
    needed = ["channel_id"]
    for req in needed:
        if req not in met.columns:
            raise SystemExit(f"Metrics CSV must include '{req}' (or map it via --metrics-cols).")

    # Optional columns; won't error if missing
    for c in ["views_30d", "audience_size", "category", "growth_30d_pct", "channel_name"]:
        if c not in met.columns:
            met[c] = None

    # 3) Join on channel_id
    merged = opps.merge(met[["channel_id","channel_name","views_30d","audience_size","category","growth_30d_pct"]],
                        left_on=channel_col, right_on="channel_id", how="left")

    # 4) Reorder to highlight useful cols
    preferred = [
        "Account.Id", "Account.Name", "Id", "Name", "StageName", "Amount", "CloseDate", "Owner.Name",
        channel_col, "channel_name", "views_30d", "audience_size", "category", "growth_30d_pct"
    ]
    cols = [c for c in preferred if c in merged.columns] + [c for c in merged.columns if c not in preferred]
    merged = merged[cols]

    merged.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(merged)} rows.")

if __name__ == "__main__":
    main()
