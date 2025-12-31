#!/usr/bin/env python3
"""
Reorder the SWE-bench Pro dataset CSV to match the chronological order
defined in swebench_pro_grouped_chronological.json
"""

import csv
import json
import sys
from pathlib import Path

# Increase CSV field size limit for large patch fields
csv.field_size_limit(sys.maxsize)

def main():
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    
    # File paths
    json_path = script_dir / "swebench_pro_grouped_chronological.json"
    csv_path = base_dir / "SWE-bench-pro-dataset.csv"
    output_path = base_dir / "SWE-bench-pro-dataset-chronological.csv"
    
    # Load the chronological order from JSON
    print(f"Loading chronological order from {json_path}...")
    with open(json_path, 'r') as f:
        chrono_data = json.load(f)
    
    # Build ordered list of instance_ids from JSON
    ordered_instance_ids = []
    for repo_name, repo_data in chrono_data["repositories"].items():
        for commit in repo_data["commits"]:
            ordered_instance_ids.append(commit["instance_id"])
    
    print(f"Found {len(ordered_instance_ids)} instances in chronological order")
    
    # Load CSV and build a lookup by instance_id
    print(f"Loading CSV from {csv_path}...")
    csv_rows_by_id = {}
    header = None
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for row in reader:
            instance_id = row['instance_id']
            csv_rows_by_id[instance_id] = row
    
    print(f"Loaded {len(csv_rows_by_id)} rows from CSV")
    
    # Verify all instance_ids from JSON exist in CSV
    missing = []
    for instance_id in ordered_instance_ids:
        if instance_id not in csv_rows_by_id:
            missing.append(instance_id)
    
    if missing:
        print(f"WARNING: {len(missing)} instance_ids from JSON not found in CSV:")
        for m in missing[:10]:
            print(f"  - {m}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    # Check for CSV rows not in JSON
    json_ids_set = set(ordered_instance_ids)
    extra_in_csv = [id for id in csv_rows_by_id.keys() if id not in json_ids_set]
    if extra_in_csv:
        print(f"WARNING: {len(extra_in_csv)} instance_ids in CSV not found in JSON:")
        for e in extra_in_csv[:10]:
            print(f"  - {e}")
        if len(extra_in_csv) > 10:
            print(f"  ... and {len(extra_in_csv) - 10} more")
    
    # Write reordered CSV
    print(f"Writing reordered CSV to {output_path}...")
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        
        written = 0
        for instance_id in ordered_instance_ids:
            if instance_id in csv_rows_by_id:
                writer.writerow(csv_rows_by_id[instance_id])
                written += 1
    
    print(f"Successfully wrote {written} rows in chronological order")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()
