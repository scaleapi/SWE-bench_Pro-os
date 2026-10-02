#!/usr/bin/env python3
"""Run mini-swe-agent on SWE-bench Pro tasks using Modal sandboxes."""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import csv
import inspect
import json
import os
import shlex
import sys
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MINI_SRC = ROOT / "mini-swe-agent" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MINI_SRC) not in sys.path:
    sys.path.insert(0, str(MINI_SRC))

import modal
from dotenv import load_dotenv

from helper_code.image_uri import get_dockerhub_image_uri
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.run.utils.save import save_traj


DEFAULT_SYSTEM_TEMPLATE = """You are a helpful assistant that can interact multiple times with a computer shell to solve programming tasks.
Your response must contain exactly ONE bash code block with ONE command, or commands connected with && or ||.

Include a THOUGHT section before your command where you explain your reasoning process.

Format:
THOUGHT: Your reasoning and analysis here

```bash
your_command_here
```

Failure to follow these rules will cause your response to be rejected."""


DEFAULT_INSTANCE_TEMPLATE = """<pr_description>
Consider the following PR description:
{{task}}
</pr_description>

<instructions>
You are working in the repository at /app.

Your task is to make source-code changes that satisfy the PR description.

Important boundaries:
- Modify regular source code files as needed.
- Do not modify tests unless the PR description explicitly asks for test changes.
- Prefer targeted commands that produce concise output.
- Avoid interactive tools.
- Directory changes are not persistent between commands, so prefix commands with cd /app when needed.

When you are finished, issue exactly this command:

```bash
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && git add -A && git diff --cached
```

This command submits the patch. Do not continue working after submitting.
</instructions>"""


DEFAULT_ACTION_OBSERVATION_TEMPLATE = """<returncode>{{output.returncode}}</returncode>
{% if output.output | length < 10000 -%}
<output>
{{ output.output -}}
</output>
{%- else -%}
<warning>
The output of your last command was too long. Try a more selective command.
</warning>
<output_head>
{{ output.output[:5000] }}
</output_head>
<elided_chars>
{{ output.output | length - 10000 }} characters elided
</elided_chars>
<output_tail>
{{ output.output[-5000:] }}
</output_tail>
{%- endif -%}"""


DEFAULT_FORMAT_ERROR_TEMPLATE = """Please always provide EXACTLY ONE action in triple backticks, found {{actions|length}} actions.

Format your response as:

THOUGHT: brief reasoning

```bash
<single command>
```"""


MODEL_SPECS: dict[str, dict[str, Any]] = {
    "claude-opus-4-8": {
        "model_name": "anthropic/claude-opus-4-8",
        "model_kwargs": {"drop_params": True},
        "set_cache_control": "default_end",
        "cost_tracking": "ignore_errors",
    },
    "claude-haiku-4-5": {
        "model_name": "anthropic/claude-haiku-4-5",
        "model_kwargs": {"drop_params": True, "temperature": 0.0, "max_tokens": 2048},
        "set_cache_control": "default_end",
        "cost_tracking": "ignore_errors",
    },
    "kimi-k2.5": {
        "model_name": "openai/kimi-k2.5",
        "model_kwargs": {"drop_params": True, "temperature": 1.0},
        "cost_tracking": "ignore_errors",
    },
}


@dataclass
class ModalSandboxConfig:
    image: str
    cwd: str = "/app"
    timeout: int = 120
    sandbox_timeout: int = 60 * 60 * 3
    env: dict[str, str] = field(default_factory=dict)
    block_network: bool = False


class ModalSandboxEnvironment:
    def __init__(self, **kwargs: Any):
        self.config = ModalSandboxConfig(**kwargs)
        app = modal.App.lookup(name="swe-bench-pro-mini-agent", create_if_missing=True)
        image = modal.Image.from_registry(self.config.image)
        self.sandbox = modal.Sandbox.create(
            image=image,
            app=app,
            timeout=self.config.sandbox_timeout,
            cpu=(1, 4),
            memory=(5 * 1024, 30 * 1024),
            block_network=self.config.block_network,
        )
        self._lock = threading.Lock()

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config)

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        workdir = cwd or self.config.cwd
        run_timeout = timeout or self.config.timeout
        token = uuid.uuid4().hex
        out_path = f"/tmp/mini_swe_agent_{token}.out"
        code_path = f"/tmp/mini_swe_agent_{token}.code"
        env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in self.config.env.items())
        wrapped = (
            f"cd {shlex.quote(workdir)} && "
            f"{env_prefix + ' ' if env_prefix else ''}"
            f"(timeout {int(run_timeout)}s bash -lc {shlex.quote(command)} > {out_path} 2>&1); "
            f"printf '%s' $? > {code_path}"
        )

        with self._lock:
            process = self.sandbox.exec("bash", "-lc", wrapped)
            process.wait()
            output = self._read_file(out_path)
            code_text = self._read_file(code_path).strip()
            self.sandbox.exec("bash", "-lc", f"rm -f {out_path} {code_path}").wait()

        try:
            returncode = int(code_text)
        except ValueError:
            returncode = process.returncode if getattr(process, "returncode", None) is not None else 1
        return {"output": output, "returncode": returncode}

    def _read_file(self, path: str) -> str:
        try:
            with self.sandbox.open(path, "r") as f:
                return f.read() or ""
        except FileNotFoundError:
            return ""

    def cleanup(self):
        try:
            result = self.sandbox.terminate()
            if inspect.isawaitable(result):
                asyncio.run(result)
        except Exception:
            pass

    def __del__(self):
        if hasattr(self, "sandbox"):
            self.cleanup()


def load_tasks(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def ensure_env():
    load_dotenv(ROOT / ".env")
    if os.getenv("MODEL_API_KEY"):
        os.environ.setdefault("OPENAI_API_KEY", os.environ["MODEL_API_KEY"])
    if os.getenv("MODEL_API_URL"):
        os.environ.setdefault("OPENAI_API_BASE", os.environ["MODEL_API_URL"])
    os.environ.setdefault("MSWEA_COST_TRACKING", "ignore_errors")
    os.environ.setdefault("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "1")


def usage_from_messages(messages: list[dict[str, Any]], cost: float, calls: int) -> dict[str, Any]:
    usage: dict[str, Any] = {
        "api_calls": calls,
        "instance_cost": cost,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    for message in messages:
        response = message.get("extra", {}).get("response", {})
        item = response.get("usage") or response.get("response", {}).get("usage") or {}
        for key in list(usage):
            if key in item and isinstance(item[key], int | float):
                usage[key] += item[key]
        # Anthropic usage is often nested under input/output token names.
        if isinstance(item.get("input_tokens"), int):
            usage["prompt_tokens"] += item["input_tokens"]
        if isinstance(item.get("output_tokens"), int):
            usage["completion_tokens"] += item["output_tokens"]
        if isinstance(item.get("cache_creation_input_tokens"), int):
            usage["cache_creation_input_tokens"] += item["cache_creation_input_tokens"]
        if isinstance(item.get("cache_read_input_tokens"), int):
            usage["cache_read_input_tokens"] += item["cache_read_input_tokens"]
    if not usage["total_tokens"]:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return usage


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def run_attempt(
    *,
    task: dict[str, Any],
    model_alias: str,
    output_dir: Path,
    dockerhub_username: str,
    redo: bool,
    command_timeout: int,
) -> dict[str, Any]:
    instance_id = task["instance_id"]
    sample_dir = output_dir / "generation" / model_alias / "sample-000"
    pred_path = sample_dir / "predictions" / instance_id / f"{instance_id}.pred"
    traj_path = sample_dir / "trajectories" / f"{instance_id}.traj.json"
    usage_path = sample_dir / "usage" / f"{instance_id}.usage.json"
    metadata_path = sample_dir / "metadata" / f"{instance_id}.metadata.json"
    log_path = sample_dir / "logs" / f"{instance_id}.log"

    if not redo and pred_path.exists() and traj_path.exists() and metadata_path.exists():
        return {
            "model": model_alias,
            "instance_id": instance_id,
            "status": "skipped_existing",
            "pred_path": str(pred_path),
        }

    started = time.time()
    model_config = MODEL_SPECS[model_alias].copy()
    if model_alias == "kimi-k2.5":
        model_config["model_name"] = "openai/" + os.getenv("MODEL_NAME", "kimi-k2.5")
        model_config.setdefault("model_kwargs", {})["api_base"] = os.getenv("MODEL_API_URL", "")

    image_uri = get_dockerhub_image_uri(instance_id, dockerhub_username, task.get("repo", ""))
    agent = None
    env = None
    exit_status = "Unknown"
    result = ""
    error_info = None

    try:
        model = get_model(config=model_config)
        env = ModalSandboxEnvironment(image=image_uri, timeout=command_timeout)
        agent = DefaultAgent(
            model,
            env,
            system_template=DEFAULT_SYSTEM_TEMPLATE,
            instance_template=DEFAULT_INSTANCE_TEMPLATE,
            action_observation_template=DEFAULT_ACTION_OBSERVATION_TEMPLATE,
            format_error_template=DEFAULT_FORMAT_ERROR_TEMPLATE,
            step_limit=250,
            cost_limit=3.0,
        )
        exit_status, result = agent.run(task["problem_statement"])
    except Exception as exc:
        exit_status = type(exc).__name__
        result = str(exc)
        error_info = {"traceback": traceback.format_exc()}
    finally:
        if env is not None:
            env.cleanup()

    pred_path.parent.mkdir(parents=True, exist_ok=True)
    pred_path.write_text(result or "")
    save_traj(
        agent,
        traj_path,
        exit_status=exit_status,
        result=result,
        extra_info=error_info,
        instance_id=instance_id,
        model_alias=model_alias,
        image_uri=image_uri,
        print_path=False,
    )
    usage = usage_from_messages(agent.messages if agent is not None else [], agent.model.cost if agent else 0.0, agent.model.n_calls if agent else 0)
    write_json(usage_path, usage)
    metadata = {
        "model": model_alias,
        "instance_id": instance_id,
        "sample_idx": 0,
        "exit_status": exit_status,
        "wall_seconds": round(time.time() - started, 3),
        "pred_path": str(pred_path),
        "traj_path": str(traj_path),
        "usage_path": str(usage_path),
        "image_uri": image_uri,
    }
    write_json(metadata_path, metadata)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata | {"status": "completed"}


def write_patches_json(output_dir: Path, model_alias: str):
    sample_dir = output_dir / "generation" / model_alias / "sample-000"
    patches = []
    for pred in sorted((sample_dir / "predictions").glob("*/*.pred")):
        instance_id = pred.parent.name
        patches.append(
            {
                "instance_id": instance_id,
                "patch": pred.read_text(),
                "prefix": f"{model_alias}_s000",
                "model": model_alias,
                "sample_idx": 0,
                "attempt_id": f"{model_alias}/sample-000/{instance_id}",
            }
        )
    write_json(sample_dir / "patches.json", patches)


def write_status_csv(output_dir: Path, rows: list[dict[str, Any]]):
    path = output_dir / "summary" / "generation_status.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "instance_id",
        "status",
        "exit_status",
        "wall_seconds",
        "pred_path",
        "traj_path",
        "usage_path",
        "image_uri",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=list(MODEL_SPECS))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dockerhub-username", default="jefzda")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--command-timeout", type=int, default=120)
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_env()
    tasks = load_tasks(args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    attempts = [(task, model) for task in tasks for model in args.models]
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_attempt = {
            executor.submit(
                run_attempt,
                task=task,
                model_alias=model,
                output_dir=args.output_dir,
                dockerhub_username=args.dockerhub_username,
                redo=args.redo,
                command_timeout=args.command_timeout,
            ): (task["instance_id"], model)
            for task, model in attempts
        }
        for future in concurrent.futures.as_completed(future_to_attempt):
            instance_id, model = future_to_attempt[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    "model": model,
                    "instance_id": instance_id,
                    "status": "runner_exception",
                    "exit_status": type(exc).__name__,
                    "wall_seconds": "",
                }
                (args.output_dir / "summary").mkdir(parents=True, exist_ok=True)
                with (args.output_dir / "summary" / "failures.jsonl").open("a") as f:
                    f.write(json.dumps(row | {"traceback": traceback.format_exc()}) + "\n")
            rows.append(row)
            print(f"{row.get('model')} {row.get('instance_id')} {row.get('status')} {row.get('exit_status', '')}")

    for model in args.models:
        write_patches_json(args.output_dir, model)
    write_status_csv(args.output_dir, rows)


if __name__ == "__main__":
    main()
