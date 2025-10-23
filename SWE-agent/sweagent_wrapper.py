import argparse
import logging
import os
import yaml
import subprocess
import json
import shutil
import numpy as np
import itertools
from pathlib import Path
from math import comb
from pydantic import BaseModel, Field
from typing import Optional

from sweagent.run.merge_predictions import merge_predictions


logger = logging.getLogger(__name__)


########################################################
######## Utility functions for SWE Agent Wrapper #######
#######################################################

class ConsolidatedReport(BaseModel):
    """
    Configuration class for the consolidated report.
    This class is used to store the top-level metrics for the SWE Agent evaluation.
    """
    samples_run: int = 0
    submitted_instances_per_sample: Optional[int] = 0
    instance_to_resolved_count: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)  # This will be populated with metrics like pass_at_k


def write_consolidated_report(output_dir: str, consolidated_report: ConsolidatedReport):
    """
    Writes the consolidated report to a JSON file.
    Args:
        output_dir (str): The directory where the consolidated report will be written.
        consolidated_report (ConsolidatedReport): The consolidated report to write.
    """
    os.makedirs(output_dir, exist_ok=True)
    consolidated_report_path = os.path.join(output_dir, "consolidated_report.json")
    with open(consolidated_report_path, "w") as f:
        json.dump(consolidated_report.model_dump(), f, indent=4)
        logger.info(f"Consolidated report written to {consolidated_report_path}")


def initialize_consolidated_report(output_dir: str):
    """
    Initializes the consolidated report in the specified output directory.
    Structure:
    {
        "samples_run": X,
        "submitted_instances_per_sample": Y,
        "instance_to_resolved_count": {
            "instance_id_1": 1,
            "instance_id_2": 0,
            ...
        },
        "metrics": {
            "pass_at_1": A, # This will be calculated later
            "pass_at_k": B  # This will be calculated later
        }
    }
    Args:
        output_dir (str): The directory where the consolidated report will be initialized.
    """
    consolidated_report_path = os.path.join(output_dir, "consolidated_report.json")
    # Backup existing consolidated report if it exists in case of re-runs
    if os.path.exists(consolidated_report_path):
        logger.warn(f"Consolidated report already exists at {consolidated_report_path}. Creating a copy at {consolidated_report_path}.bak")
        shutil.copy2(consolidated_report_path, consolidated_report_path + ".bak")

    consolidated_report = ConsolidatedReport()

    write_consolidated_report(output_dir, consolidated_report)
    logger.info(f"Initialized consolidated report at {consolidated_report_path}")
    return consolidated_report


def update_top_level_metrics(config: dict, output_dir: str, consolidated_report: ConsolidatedReport, sample_num: int):
    """
    Updates the top-level metrics in the consolidated report based on the evaluation results.
    

    Args:
        config (dict): The configuration dictionary containing the evaluation settings.
        output_dir (str): The directory where the consolidated report will be written.
        consolidated_report (ConsolidatedReport): The consolidated report to update.
        sample_num (int): The sample number being processed.
    Returns:
        consolidated_report (ConsolidatedReport): The updated consolidated report.
    """
    consolidated_report.samples_run += 1
    sample_results_path = os.path.join(output_dir, f"sample_{sample_num}", \
                                       f"sample_{sample_num}.swebench_evaluation.json")
    if not os.path.exists(sample_results_path):
        logger.error(f"Sample results file not found at {sample_results_path}. Re-running swebench eval for sample {sample_num}.")
        if config.get("swebench_command"):
            logger.info("Running SWE Bench evaluation...")
            run_swebench_evaluation(config, output_dir + f"/sample_{sample_num}")

        return consolidated_report
    with open(sample_results_path, "r") as fs:
        sample_results = json.load(fs)

        if  sample_results.get("submitted_instances") > consolidated_report.submitted_instances_per_sample:
            # Update the submitted instances per sample to be the maximum of the current and previous values
            if consolidated_report.submitted_instances_per_sample > 0:
                logger.warn(f"Sample {sample_num} has more submitted instances ({sample_results.get('submitted_instances')}) \
                            than previously recorded ({consolidated_report.submitted_instances_per_sample}). This may indicate an \
                            issue with this evaluation.")
            consolidated_report.submitted_instances_per_sample = sample_results.get("submitted_instances")

        for instance_id in sample_results.get("resolved_ids", []):
            # Update the instances to resolved count dictionary
            consolidated_report.instance_to_resolved_count[instance_id] = 1 + \
                                                    consolidated_report.instance_to_resolved_count.get(instance_id, 0)
        
        for instance_id in sample_results.get("unresolved_ids", []):
            # If the instance is unresolved, track it with a count of 0 for now.
            if instance_id not in consolidated_report.instance_to_resolved_count:
                consolidated_report.instance_to_resolved_count[instance_id] = 0

    # Write the updated consolidated report back to the file
    write_consolidated_report(output_dir, consolidated_report)
    return consolidated_report


def estimate_pass_at_k(num_samples, num_correct, k):
    """
    Estimates pass@k of each problem and returns them in an array.
    Reference: https://github.com/huggingface/evaluate/blob/main/metrics/code_eval/code_eval.py
    Args:
        num_samples (int or list): Number of samples submitted for each problem.
        num_correct (list): Number of correct solutions for each problem.
        k (int): The number of attempts to consider for the Pass@k metric.
    """

    def estimator(n: int, c: int, k:int) -> float:
        """Calculates 1 - comb(n - c, k) / comb(n, k)."""
        if n - c < k:
            return 1.0
        return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))

    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    return np.array([estimator(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)])


def calculate_pass_at_k(output_dir: str, k: int, consolidated_report: ConsolidatedReport) -> ConsolidatedReport:
    """
    Calculates the Pass@1 and Pass@k metrics, both overall and per-instance,
    and stores them in the consolidated report.

    Args:
        output_dir (str): The directory where the consolidated report is stored.
        k (int): The number of attempts to consider for the Pass@k metric.
        consolidated_report (ConsolidatedReport): The consolidated report containing the evaluation results.
    Returns:
        consolidated_report (ConsolidatedReport): The updated consolidated report with metrics.
    """
    if not consolidated_report.instance_to_resolved_count:
        logger.warn("No instances found in the consolidated report. Cannot calculate pass@k.")
        return consolidated_report

    num_samples = consolidated_report.samples_run
    instance_ids = list(consolidated_report.instance_to_resolved_count.keys())
    correct_counts = list(consolidated_report.instance_to_resolved_count.values())

    # Calculate pass@1 and pass@k scores for each instance
    pass_at_1_scores = estimate_pass_at_k(num_samples, correct_counts, 1)
    pass_at_k_scores = estimate_pass_at_k(num_samples, correct_counts, k)

    # Store per-instance metrics
    per_instance_metrics = {}
    for i, instance_id in enumerate(instance_ids):
        per_instance_metrics[instance_id] = {
            "pass_at_1": pass_at_1_scores[i],
            f"pass_at_{k}": pass_at_k_scores[i]
        }
    consolidated_report.metrics["per_instance"] = per_instance_metrics

    # Calculate and store overall metrics
    overall_pass_at_1 = np.mean(pass_at_1_scores)
    logger.info(f"✅ Overall pass@1: {overall_pass_at_1:.4f}")
    consolidated_report.metrics["pass_at_1"] = overall_pass_at_1

    overall_pass_at_k = np.mean(pass_at_k_scores)
    logger.info(f"✅ Overall pass@{k}: {overall_pass_at_k:.4f}")
    consolidated_report.metrics[f"pass_at_{k}"] = overall_pass_at_k

    # Write the final report with all metrics included
    write_consolidated_report(output_dir, consolidated_report)
    return consolidated_report


def convert_json_to_jsonl(input_json_path: Path, output_jsonl_path: Path) -> None:
    """
    Converts a JSON file (where top-level keys are instance_ids)
    into a JSONL file with 'instance_id', 'model_name_or_path', and 'model_patch' fields
    required for SWE Bench evaluation.

    Args:
        input_json_path (Path): The path to the input JSON file.
        output_jsonl_path (Path): The path for the output JSONL file.
    """
    if not input_json_path.is_file():
        logger.error(f"Error: Input file not found at '{input_json_path}'")
        return
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from '{input_json_path}'.")
        return

    output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_jsonl_path, 'w', encoding='utf-8') as f:
        for instance_id, prediction_data in data.items():
            output_obj = {
                "instance_id": instance_id,
                "model_name_or_path": prediction_data.get("model_name_or_path", "unknown_model"),
                "model_patch": str(prediction_data.get("model_patch", "")) if prediction_data.get("model_patch") is not None else ""
            }
            f.write(json.dumps(output_obj) + '\n')

    logger.info(f"Successfully converted '{input_json_path}' to '{output_jsonl_path}'")


def run_command(command: str):
    """
    Run a command in the shell and return the output.
    Args:
        command (str): The command to run as a string
    """
    try:
        return_code = subprocess.call(command, shell=True)
        if return_code != 0:
            logger.error(f"Command failed with return code: {return_code}", exc_info=True)
            raise RuntimeError(
                f"Command '{command}' failed with return code {return_code}"
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing command: {e}", exc_info=True)
        raise e


def run_sweagent(config: dict, output_dir: str):
    """
    Runs the SWE Agent with the provided configuration.
    Args:
        config (dict): Configuration with SWE-agent and SWE-bench commands
        output_dir (str): The directory where the SWE Agent will store its output
    """
    
    command = config.get("sweagent_command", "")
    if not command:
        raise ValueError("Command to run SWE Agent is not specified in the configuration.")
    command = command.format(output_dir=output_dir)
    logger.info(f"Running SWE Agent with command: {command}")
    run_command(command)
    
    
    if config.get("swebench_command"):
        logger.info("Running SWE Bench evaluation...")
        run_swebench_evaluation(config, output_dir)


def run_swebench_evaluation(config: dict, output_dir: str):
    """
    Runs the evaluation using swebench
    Args:
        config (dict): Configuration with SWE-bench command
        output_dir (str): The directory where the SWE Bench will store its output
    """
    # Run swebench from predictions path to store results in the same directory
    current_working_dir = os.getcwd()
    predictions_path = Path(output_dir)
    os.chdir(predictions_path)

    if not os.path.exists("preds.json"):
        # If preds.json does not exist, we need to merge predictions
        logger.info(f"Predictions file not found at {predictions_path}/preds.json, merging predictions...")
        merge_predictions([Path(".")], Path("preds.json"))

    logger.info(f"Converting predictions from preds.json to JSONL format")
    convert_json_to_jsonl(Path("preds.json"), Path("preds.jsonl"))

    swebench_command = config.get("swebench_command", "").format(output_dir=predictions_path)
    command = "python -m " + swebench_command
    logger.info(f"Running SWE Bench with command: {command}")
    run_command(command)

    # CD back to the original working directory
    os.chdir(current_working_dir)


def run_sweagent_wrapper(config):
    """
    Runs the SWE Agent Wrapper with the provided configuration.

    Args:
        config (dict): Configuration with SWE-agent and SWE-bench commands
    """
    logger.info("Starting SWE Agent Wrapper")
    if not config.get("output_dir"):
        raise ValueError("Output directory is not specified in the configuration at the top level.")

    output_dir = config["output_dir"]
    if config.get("num_samples"):
        num_samples = config["num_samples"]
        
        consolidated_report = initialize_consolidated_report(output_dir)
        for i in range(num_samples):
            logger.info(f"Running SWE Agent Wrapper for sample {i + 1}/{num_samples}")
            if i + 1 >= config.get("start_sample", 0):
                # If start_sample is specified, skip to that sample
                run_sweagent(config, output_dir + f"/sample_{i + 1}")
            consolidated_report = update_top_level_metrics(config, output_dir, consolidated_report, i + 1)
        logger.info("Calculating Pass@1 and Pass@k metrics")
        consolidated_report = calculate_pass_at_k(output_dir, num_samples, consolidated_report)
        pretty_printed_report = consolidated_report.model_dump_json(indent=4)
        logger.info(f"All samples processed. Consolidated report: {pretty_printed_report}")
    else:
        logger.info("Running SWE Agent Wrapper for a single sample")
        run_sweagent(config, output_dir)


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="SWE Agent Wrapper CLI")
    parser.add_argument(
        "config",
        type=str,
        help="Name of configuration file for sweagent in sweagent_wrapper_configs/ directory",
    )

    args = parser.parse_args()

    # Allow for passing config name without .yaml extension
    if not (args.config.endswith(".yaml") or args.config.endswith(".yml")):
        args.config += ".yaml"

    if not os.path.exists(os.path.join("sweagent_wrapper_configs", args.config)):
        logger.error(f"Configuration file not found under sweagent_wrapper_configs: {args.config}")
        raise FileNotFoundError(f"Configuration file not found under sweagent_wrapper_configs: {args.config}")
    with open(os.path.join("sweagent_wrapper_configs", args.config), "r") as f:
        config = yaml.safe_load(f)

    run_sweagent_wrapper(config)


if __name__ == "__main__":
    main()
