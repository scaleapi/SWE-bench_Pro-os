#!/usr/bin/env python3
"""
Script to create a {model}_preds.json file by collecting prediction dictionaries
from .pred or .patch files in trajectory folders.

Usage:
    python collect_predictions.py <base_folder> <model>

Example:
    python collect_predictions.py /path/to/sweagent_results/sweap_eval_1023 claude-45sonnet
"""

import argparse
import json
from pathlib import Path


def load_pred_file(pred_file_path, instance_id):
    """Load and parse a .pred or .patch file."""
    try:
        with open(pred_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
            # If it's a .patch file, create a dictionary with the patch content
            if pred_file_path.suffix == '.patch':
                return {
                    'instance_id': instance_id,
                    'model_patch': content
                }
            
            # For .pred files, try to parse as JSON first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # If JSON fails, try to evaluate as Python dict
                # Note: This is potentially unsafe with untrusted input
                return eval(content)
    except Exception as e:
        print(f"Error loading {pred_file_path}: {e}")
        return None


def collect_predictions(base_folder, model):
    """
    Collect all prediction dictionaries from trajectory folders.
    
    Args:
        base_folder: Base directory path
        model: Model name
    
    Returns:
        List of prediction dictionaries
    """
    predictions = []
    
    # Build path to trajectory folder
    traj_folder = Path(base_folder) / model / "traj"
    
    if not traj_folder.exists():
        print(f"Trajectory folder not found: {traj_folder}")
        return predictions
    
    print(f"Scanning trajectory folder: {traj_folder}")
    
    # Iterate through all subdirectories in traj folder
    for instance_folder in traj_folder.iterdir():
        if instance_folder.is_dir():
            instance_id = instance_folder.name
            
            # Look for .pred file first, then .patch file
            pred_files = list(instance_folder.glob("*.pred"))
            
            if not pred_files:
                pred_files = list(instance_folder.glob("*.patch"))
            
            if pred_files:
                # Use the first file found
                pred_file = pred_files[0]
                print(f"Processing: {instance_id} (using {pred_file.suffix})")
                
                # Load the prediction dictionary
                pred_dict = load_pred_file(pred_file, instance_id)
                if pred_dict is not None:
                    predictions.append(pred_dict)
                else:
                    print(f"Failed to load prediction from: {pred_file}")
            else:
                print(f"No .pred or .patch file found in: {instance_folder}")
    
    return predictions


def main():
    """Main function to collect predictions and save to JSON file."""
    parser = argparse.ArgumentParser(
        description='Collect prediction dictionaries from trajectory folders and save to JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  %(prog)s /path/to/sweagent_results/sweap_eval_1023 claude-45sonnet
        """
    )
    parser.add_argument('base_folder', type=str,
                        help='Base directory containing model results')
    parser.add_argument('model', type=str,
                        help='Model name (subdirectory name within base_folder)')
    
    args = parser.parse_args()
    
    base_folder = Path(args.base_folder)
    model = args.model
    
    print(f"Base folder: {base_folder}")
    print(f"Model: {model}")
    
    if not base_folder.exists():
        print(f"Error: Base folder does not exist: {base_folder}")
        return 1
    
    predictions = collect_predictions(base_folder, model)
    
    print(f"\nCollected {len(predictions)} predictions")
    
    if len(predictions) == 0:
        print("Warning: No predictions were collected")
        return 1
    
    # Use base folder name in output filename
    base_name = base_folder.name
    output_filename = f"{model}_preds_{base_name}.json"
    
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
        
        print(f"\nSuccessfully created: {output_filename}")
        print(f"Contains {len(predictions)} prediction dictionaries")
        return 0
    
    except Exception as e:
        print(f"Error saving to {output_filename}: {e}")
        return 1


if __name__ == "__main__":
    exit(main())