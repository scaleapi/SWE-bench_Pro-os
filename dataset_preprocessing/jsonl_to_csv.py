#!/usr/bin/env python3
"""Convert a JSONL dataset file to CSV.

List-valued columns (e.g. fail_to_pass, eval_scripts) are kept as JSON strings.

Usage:
    uv run python dataset_preprocessing/jsonl_to_csv.py --input artifacts/python_dataset.jsonl --output artifacts/python_dataset.csv
    uv run python dataset_preprocessing/jsonl_to_csv.py --input artifacts/python_dataset.jsonl --output artifacts/python_dataset.csv --limit 10
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="Input JSONL path.")
    p.add_argument("--output", help="Output CSV path. Defaults to input path with .csv extension.")
    p.add_argument("--limit", type=int, default=None, help="Max number of rows to process.")
    args = p.parse_args()

    inp = Path(args.input)
    out = Path(args.output) if args.output else inp.with_suffix(".csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [l for l in inp.read_text().splitlines() if l.strip()]
    if args.limit is not None:
        lines = lines[: args.limit]
    records = [json.loads(l) for l in lines]

    df = pd.DataFrame(records)
    for col in df.columns:
        if df[col].apply(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].apply(json.dumps)

    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows → {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
