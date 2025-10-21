# SWE-agent for SWE-bench Pro

This guide explains how to run SWE-agent on the SWE-bench Pro dataset using Modal. This setup supports both direct command-line execution and a dockerized wrapper.

For details about SWE-agent implementation, please see https://github.com/SWE-agent/SWE-agent.

## Prerequisites

Before getting started, ensure you have the following:

- **Python 3.8+** with pip installed
- **Docker** (Recommended, for the dockerized wrapper setup)
- **Just** command runner (if using the dockerized wrapper setup)
- **Modal account** with access credentials (request via #it-help slack channel)
- **API access** to a compatible LLM (e.g., OpenAI API, Anthropic Claude API, or hosted model endpoint)
- **DockerHub username** for generating the instances.yaml file

# Installation

## Install SWE-agent
```bash
pip install -e .
```

## Create Required Directories
SWE-agent expects certain directories to exist. Create them if they don't already exist:
```bash
mkdir -p trajectories
```

## Apply SWE-Rex Patches
After installing SWE-agent, you need to apply custom patches to the SWE-Rex installation. These patches modify the installed SWE-Rex package to work properly with SWE-bench Pro.

The `patch.py` script will:
1. Locate your SWE-Rex installation (in your Python environment's site-packages)
2. Back up the original files with a `.bak` extension
3. Copy the patched versions over the installed files

To apply the patches:

```bash
cd swerex_patches
python patch.py
```

You'll be prompted to confirm each patch. To skip prompts and apply all patches automatically:

```bash
python patch.py --yes
```

**Note**: Currently patches `swerex/deployment/modal.py` to customize Modal deployment behavior for SWE-bench Pro.

# Generate Instances
Before running SWE-agent, you must first generate the instance YAML file from the SWE-bench Pro dataset. This file contains all the necessary information for each instance including Docker image names, problem statements, and repository details.

Run the generation script:
```bash
python helper_code/generate_sweagent_instances.py --dockerhub_username <your-dockerhub-username>
```

This will create `SWE-agent/data/instances.yaml` with all instances from the SWE-bench Pro test split. You can customize the output path:
```bash
python helper_code/generate_sweagent_instances.py \
    --dockerhub_username <your-dockerhub-username> \
    --output_path path/to/custom_instances.yaml
```

**Note**: The generated instances.yaml file is what you'll reference in the `--instances.path` parameter when running SWE-agent (see examples below).

# Configure Environment Variables

## For dockerized setup (recommended)

Before running SWE-agent, create a `.env` file in the `SWE-agent/` directory to store your API credentials. These environment variables will be used in your configuration files.

Create `SWE-agent/.env` with the following content:
```
OPENAI_API_KEY=<your-api-key>
OPENAI_BASE_URL=<your-api-base-url>  # Optional, only if using a custom endpoint
```

## For non-dockerized setup



**Note**: Despite the variable names, these can be used with any LLM provider:
- For standard API providers: set `OPENAI_API_KEY` to your API key
- For custom endpoints: set `OPENAI_BASE_URL` to your API endpoint
- For hosted models: set both variables to point to your hosted endpoint

These variables are referenced in the config files as `$OPENAI_API_KEY` and `$OPENAI_BASE_URL`.

# Run
For batch run, the scripts can take input `json`, `jsonl` or `yaml` files.

```
INSTANCE_PATH=xx
OUTPUT_PATH=xx


sweagent run-batch \
    --config config/tool_use.yaml \
    --output_dir $OUTPUT_PATH \
    --num_workers 30 \
    --random_delay_multiplier 1 \
    --instances.type file \
    --instances.path $INSTANCE_PATH \
    --instances.slice :300 \
    --instances.shuffle=False \
    --instances.deployment.type=modal \
    --agent.model.name claude-3-7-sonnet-20250219 \
    --agent.model.api_base $OPENAI_BASE_URL \
    --agent.model.api_key $OPENAI_API_KEY
```

This will generate the patches, which can then be evaluated use the same scripts we use for evaluating SWEAP.

# Running with Dockerized Wrapper Setup

In order to run swe-agent using a docker container which handles installing all dependencies and patches as well as a single entrypoint script, follow these steps

## Setup Modal
First, get access to modal via the #it-help slack channel.

Run the following commands to store modal credentials (if you want to run swe-agent with modal):
```
pip install modal
modal setup # and follow the prompts to generate your token and secret
```

After running these steps, you should be able to see a token ID and secret in  `~/.modal.toml`:
EG:
```
[your-workspace-name]
token_id = <token id>
token_secret = <token secret>
active = true
```
## Create a .env file
In the SWE-agent directory, create an .env file and populate it with your OpenAI API Key:

```
OPENAI_API_KEY=<your API key>
```
This env will be mounted into the docker container, so it can be used to set any other relevant environment variables

## Create SWE-Agent Wrapper Config

To easily be able to execute swe-agent runs, create a YAML config under the `sweagent_wrapper_configs/` directory.
The config structure should look like:

```
output_dir: sweagent_results/sweagent/test # REQUIRED: This writes results to sweagent_results/sweagent/test, can be changed to any path under sweagent_results/
sweagent_command: |
  sweagent run-batch \
    --config config/tool_use.yaml \
    --output_dir {output_dir} \
    --num_workers 10 \
    --random_delay_multiplier 1 \
    --instances.type file \
    --instances.path data/instances.yaml \
    --instances.slice :10 \
    --instances.shuffle=False \
    --instances.deployment.type=modal \
    --agent.model.name anthropic/claude-3-7-sonnet-20250219 \
    --agent.model.api_base $OPENAI_BASE_URL \
    --agent.model.api_key $OPENAI_API_KEY # Make sure this is set in the .env file
```

The command section refers to the exact swe-agent command which will be executed. Please actively refer to https://swe-agent.com/latest/usage/batch_mode/ for command line arguments when running batch commands for swe-agent.
The above examples runs sweagent on 10 sweap instances.

**For a working example**: See `sweagent_wrapper_configs/example_config.yaml` which runs SWE-agent on 10 instances from the generated instances.yaml file (type: file, no shuffle) using modal deployment with 10 workers and a delay multiplier of 1.
To run on all instances, remove the `--instances.slice :10 \` line from the config.

### Configurable Agent Options

You can set additional agent configuration options in your wrapper config or via command-line flags. Common options include:

**Model Limits:**
- `--agent.model.per_instance_cost_limit <value>` - Cost limit per instance in dollars (default: 3.0, set to 0 to disable)
- `--agent.model.total_cost_limit <value>` - Total cost limit across all instances (default: 0, disabled)
- `--agent.model.per_instance_call_limit <value>` - Maximum LLM calls per instance (default: 0, disabled)

**Model Parameters:**
- `--agent.model.temperature <value>` - Sampling temperature (default: 0.0)
- `--agent.model.top_p <value>` - Sampling top-p (default: 1.0)
- `--agent.model.max_input_tokens <value>` - Override max input tokens
- `--agent.model.max_output_tokens <value>` - Override max output tokens

**Note for litellm proxies:** If cost tracking doesn't work with your setup, disable cost limits and use call limits instead:
```bash
--agent.model.per_instance_cost_limit 0 \
--agent.model.total_cost_limit 0 \
--agent.model.per_instance_call_limit 200
```

For a complete list of all configuration options, refer to:
- Model options: `sweagent/agent/models.py` - `GenericAPIModelConfig` class
- All SWE-agent options: See the [official SWE-agent documentation](https://github.com/SWE-agent/SWE-agent)

## Build and Run Docker Container
Now, to actually run the dockerized setup, run the following commands from the `SWE-agent/` directory:

```
just build && just run
```

This command will build a docker image (sweagent-image) with a tag of your username, and run the docker container.

**NOTE: You don't have to build the image each time, you can run using just run in the future if your only changes are config changes. See the "Config file or Command Changes" section**

## Run sweagent to generate predictions!
Finally, once inside the docker container you can run the wrapper script with your curated wrapper config which is under `sweagent_wrapper_configs/` (you don't need to pass in the full path, the CLI is configured to only check that directory):

```
python sweagent_wrapper.py <your config.yaml>
```

EG:
```
python sweagent_wrapper.py wrapper_config.yaml
```
OR (without the yaml extension)
```
python sweagent_wrapper.py wrapper_config
```
will execute the sweagent and swebench commands defined in `sweagent_wrapper_configs/wrapper_config.yaml`

You should be able to see the run logs actively your console, and final predictions will be written to `{--output_dir}/preds.json`. 

### Config file or Command Changes

The files under `sweagent_wrapper_configs/` and `config/` are synced into the **running docker container** automatically (changes will be reflected when files are saved). So configs as well as commands to sweagent can be changed without any rebuilding required.