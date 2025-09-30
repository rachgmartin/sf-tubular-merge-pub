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
import sys
from typing import Dict, Optional

import pandas as pd


def parse_colmap(arg: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not arg:
        return mapping
    pairs = [p.strip() for p in arg.split(",") if p.strip()]
    for pair in pairs:
        if ":" not in pair:
            raise ValueError(f"Bad metrics column pair: {pair}. Use new_name:existing_header")
        new, old = pair.split(":", 1)
        mapping[new.strip()] = old.strip()
    return mapping


def _find_channel_column(opps: pd.DataFrame) -> Optional[str]:
    for col in ["Account.YouTube_Channel_ID__c", "YouTube_Channel_ID__c", "channel_id", "Channel_ID__c"]:
        if col in opps.columns:
            return col
    return None


def _select_account_column(opps: pd.DataFrame) -> Optional[str]:
    for col in ["Account.Name", "account_name", "Account"]:
        if col in opps.columns:
            return col
    return None


def merge_data(
    opps_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    map_df: Optional[pd.DataFrame] = None,
    metrics_colmap: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """Merge Salesforce opportunities and Tubular metrics data frames."""

    opps = opps_df.copy()
    metrics = metrics_df.copy()
    metrics_colmap = metrics_colmap or {}

    channel_col = _find_channel_column(opps)
    map_used = False

    if channel_col is None:
        if map_df is None:
            raise ValueError(
                "Opps CSV has no channel_id column. Provide a channel map with account_name and channel_id."
            )
        cmap = map_df.copy()
        if "account_name" not in cmap.columns or "channel_id" not in cmap.columns:
            raise ValueError("channel_map.csv must include: account_name, channel_id")
        acct_col = _select_account_column(opps)
        if acct_col is None:
            raise ValueError("Couldn't find Account.Name column in opps to join with channel_map.")
        opps = opps.merge(
            cmap[["account_name", "channel_id"]],
            left_on=acct_col,
            right_on="account_name",
            how="left",
        )
        channel_col = "channel_id"
        map_used = True

    if metrics_colmap:
        metrics = metrics.rename(columns={v: k for k, v in metrics_colmap.items()})

    if "channel_id" not in metrics.columns:
        raise ValueError("Metrics CSV must include 'channel_id' (or map it via --metrics-cols).")

    for c in ["views_30d", "audience_size", "category", "growth_30d_pct", "channel_name"]:
        if c not in metrics.columns:
            metrics[c] = None

    merged = opps.merge(
        metrics[[
            "channel_id",
            "channel_name",
            "views_30d",
            "audience_size",
            "category",
            "growth_30d_pct",
        ]],
        left_on=channel_col,
        right_on="channel_id",
        how="left",
    )

    preferred = [
        "Account.Id",
        "Account.Name",
        "Id",
        "Name",
        "StageName",
        "Amount",
        "CloseDate",
        "Owner.Name",
        channel_col,
        "channel_name",
        "views_30d",
        "audience_size",
        "category",
        "growth_30d_pct",
    ]
    cols = [c for c in preferred if c in merged.columns] + [c for c in merged.columns if c not in preferred]
    merged = merged[cols]

    merged.attrs["channel_column"] = channel_col
    merged.attrs["map_used"] = map_used

    return merged


def main(argv=None):
    """Run the CLI entrypoint.

    Streamlit executes the application script via ``runpy`` which causes any
    top-level modules to be re-executed as part of the reload cycle. When that
    happens ``argparse`` would normally raise an error because we did not
    provide the required CLI arguments. Instead of crashing (and spamming the
    Streamlit logs) we detect the empty-argument case and simply print the
    usage information.
    """

    ap = argparse.ArgumentParser()
    ap.add_argument("--opps", required=True)
    ap.add_argument("--metrics", required=True, help="Tubular CSV export")
    ap.add_argument("--map", required=False, help="Optional channel_map.csv to attach channel_id by Account.Name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--metrics-cols", required=False, default="", help="Header mapping new:old,new:old ...")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        ap.print_help()
        return

    args = ap.parse_args(argv)

    opps = pd.read_csv(args.opps)
    metrics = pd.read_csv(args.metrics)
    cmap_df = pd.read_csv(args.map) if args.map else None

    try:
        colmap = parse_colmap(args.metrics_cols)
        merged = merge_data(opps, metrics, map_df=cmap_df, metrics_colmap=colmap)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    merged.to_csv(args.out, index=False)
    channel_col = merged.attrs.get("channel_column", "channel_id")
    print(f"Wrote {args.out} with {len(merged)} rows (joined on '{channel_col}').")


if __name__ == "__main__":
    main()
