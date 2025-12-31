#!/usr/bin/env python3
"""
Script to add base_dockerfile and instance_dockerfile columns to the CSV.
Reads dockerfile contents from the dockerfiles/ directory structure.
"""

import os
import pandas as pd
from pathlib import Path

def load_dockerfile(dockerfiles_dir, dockerfile_type, instance_id):
    """
    Load dockerfile content for a given instance.
    
    Args:
        dockerfiles_dir: Base dockerfiles directory
        dockerfile_type: 'base_dockerfile' or 'instance_dockerfile'
        instance_id: The instance ID
        
    Returns:
        str: Dockerfile content or empty string if not found
    """
    dockerfile_path = Path(dockerfiles_dir) / dockerfile_type / instance_id / "Dockerfile"
    if dockerfile_path.exists():
        with open(dockerfile_path, 'r') as f:
            return f.read()
    else:
        print(f"Warning: Dockerfile not found: {dockerfile_path}")
        return ""


def main():
    # Paths
    csv_path = "SWE-bench-pro-dataset.csv"
    dockerfiles_dir = "dockerfiles"
    output_path = "SWE-bench-pro-dataset-with-dockerfiles.csv"
    
    print(f"Loading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows")
    print(f"Columns: {df.columns.tolist()}")
    
    # Check if columns already exist
    if 'base_dockerfile' in df.columns and 'instance_dockerfile' in df.columns:
        print("Columns already exist! Exiting.")
        return
    
    # Add new columns
    base_dockerfiles = []
    instance_dockerfiles = []
    
    missing_base = 0
    missing_instance = 0
    
    for idx, row in df.iterrows():
        instance_id = row['instance_id']
        
        base_content = load_dockerfile(dockerfiles_dir, 'base_dockerfile', instance_id)
        instance_content = load_dockerfile(dockerfiles_dir, 'instance_dockerfile', instance_id)
        
        if not base_content:
            missing_base += 1
        if not instance_content:
            missing_instance += 1
            
        base_dockerfiles.append(base_content)
        instance_dockerfiles.append(instance_content)
        
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1}/{len(df)} rows...")
    
    df['base_dockerfile'] = base_dockerfiles
    df['instance_dockerfile'] = instance_dockerfiles
    
    print(f"\nSummary:")
    print(f"  Total rows: {len(df)}")
    print(f"  Missing base_dockerfile: {missing_base}")
    print(f"  Missing instance_dockerfile: {missing_instance}")
    
    # Save to new CSV
    print(f"\nSaving to {output_path}...")
    df.to_csv(output_path, index=False)
    print(f"Done! New CSV saved to {output_path}")
    
    # Show file size comparison
    original_size = os.path.getsize(csv_path) / (1024 * 1024)
    new_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nFile size: {original_size:.2f} MB -> {new_size:.2f} MB")


if __name__ == "__main__":
    main()
