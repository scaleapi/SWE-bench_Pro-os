#!/usr/bin/env bash
# Usage:
#   ./test_instance.sh <instance_id|index>
#   ./test_instance.sh <instance_id|index> --dataset <path/to/dataset.jsonl>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DOCKERFILE="$SCRIPT_DIR/../artifacts/Dockerfile.system-deps"
BASE_IMAGE="swebench-system-deps"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <instance_id|index> [--dataset <path>]"
    exit 1
fi

ARG="$1"
shift

DATASET="$SCRIPT_DIR/../artifacts/python_dataset.jsonl"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 <instance_id|index> [--dataset <path>]"
            exit 1
            ;;
    esac
done

DATASET="$(realpath "$DATASET")"

# Resolve entry: numeric index or instance_id string
if [[ "$ARG" =~ ^[0-9]+$ ]]; then
    ENTRY=$(python3 -c "
import sys, json
lines = open('$DATASET').readlines()
idx = int('$ARG')
if idx >= len(lines):
    sys.exit(f'Index {idx} out of range (dataset has {len(lines)} entries)')
print(lines[idx].strip())
")
else
    ENTRY=$(python3 -c "
import sys, json
for line in open('$DATASET'):
    d = json.loads(line)
    if d['instance_id'] == '$ARG':
        print(line.strip())
        sys.exit(0)
sys.exit('instance_id not found: $ARG')
")
fi

# Extract fields
REPO=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['repo'])" "$ENTRY")
BASE_COMMIT=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['base_commit'])" "$ENTRY")
INSTANCE_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['instance_id'])" "$ENTRY")
BEFORE_CMD=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['before_repo_set_cmd'])" "$ENTRY")
SETUP_SCRIPT=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['setup_script'])" "$ENTRY")
EVAL_SCRIPT=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['eval_scripts'][0])" "$ENTRY")

# Short tag: last 12 chars of instance_id, lowercased, sanitised
SHORT_TAG=$(echo "$INSTANCE_ID" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | tail -c 20)
IMAGE_TAG="swebench-test-$SHORT_TAG"

echo "==> Instance : $INSTANCE_ID"
echo "==> Repo     : $REPO"
echo "==> Commit   : $BASE_COMMIT"
echo "==> Image    : $IMAGE_TAG"

# Build base image if missing
if ! docker image inspect "$BASE_IMAGE" &>/dev/null; then
    echo "==> Building base image $BASE_IMAGE from $BASE_DOCKERFILE ..."
    docker build -t "$BASE_IMAGE" -f "$BASE_DOCKERFILE" "$(dirname "$BASE_DOCKERFILE")"
fi

# Create temp build context
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

printf '%s' "$SETUP_SCRIPT" > "$TMPDIR/setup.sh"
printf '%s' "$EVAL_SCRIPT"  > "$TMPDIR/eval.sh"
printf '%s' "$BEFORE_CMD"   > "$TMPDIR/before_repo_set_cmd.sh"
# Write patch directly from Python to preserve trailing newline (shell $() strips it)
python3 -c "
import json, sys
entry = json.loads(sys.argv[1])
with open(sys.argv[2], 'w') as f:
    f.write(entry['patch'])
" "$ENTRY" "$TMPDIR/patch.diff"
chmod +x "$TMPDIR/setup.sh" "$TMPDIR/eval.sh" "$TMPDIR/before_repo_set_cmd.sh"

# Entrypoint: run eval before patch, apply patch, run eval after patch, then drop to shell
cat > "$TMPDIR/entrypoint.sh" <<'ENTRYPOINT'
#!/usr/bin/env bash
set -euo pipefail

source /opt/venv/bin/activate 2>/dev/null || true

run_eval() {
    local label="$1"   # "before" or "after"
    local outdir="/workspace/$label"
    mkdir -p "$outdir"
    # eval.sh writes run_script.sh, parser.py, stdout.log, stderr.log, output.json
    # all relative to /workspace — run it from a subshell that redirects /workspace
    # by temporarily symlinking /workspace to the target dir
    (
        cd "$outdir"
        # Override /workspace by running eval.sh with a wrapper that cd's first.
        # eval.sh uses hardcoded /workspace paths, so bind-mount isn't available here;
        # instead we patch the paths via a sed wrapper script.
        sed "s|/workspace/|${outdir}/|g" /workspace/eval.sh > "$outdir/eval_run.sh"
        chmod +x "$outdir/eval_run.sh"
        bash "$outdir/eval_run.sh" > "$outdir/eval.log" 2>&1 || true
    )
    echo "Done. Results in /workspace/$label/"
}

echo "========================================================"
echo " Running eval BEFORE patch ..."
echo "========================================================"
run_eval before

echo ""
echo "========================================================"
echo " Applying patch ..."
echo "========================================================"
git apply /workspace/patch.diff
echo "Patch applied."

echo ""
echo "========================================================"
echo " Running eval AFTER patch ..."
echo "========================================================"
run_eval after

echo ""
echo "========================================================"
echo " Summary"
echo "========================================================"
echo "  Before results : /workspace/before/"
echo "  After results  : /workspace/after/"
echo "  (output.json, stdout.log, stderr.log, eval.log in each)"
echo ""
echo " Dropping into shell. The venv is active."
exec bash
ENTRYPOINT
chmod +x "$TMPDIR/entrypoint.sh"

# Write Dockerfile
cat > "$TMPDIR/Dockerfile" <<DOCKERFILE
FROM $BASE_IMAGE

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:\$PATH"

# Clone repo and check out base commit
RUN git clone https://github.com/${REPO} /app
WORKDIR /app
RUN git checkout ${BASE_COMMIT}

# Apply before_repo_set_cmd (checks out test files from a later commit)
COPY before_repo_set_cmd.sh /workspace/before_repo_set_cmd.sh
RUN bash /workspace/before_repo_set_cmd.sh

# Run setup script (installs venv + dependencies)
COPY setup.sh /workspace/setup.sh
RUN bash /workspace/setup.sh

# Install runtime files
COPY eval.sh /workspace/eval.sh
COPY patch.diff /workspace/patch.diff
COPY entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/eval.sh /workspace/entrypoint.sh

WORKDIR /app
CMD ["/workspace/entrypoint.sh"]
DOCKERFILE

echo "==> Building test image $IMAGE_TAG ..."
docker build -t "$IMAGE_TAG" "$TMPDIR"

echo ""
echo "==> Running evaluation (before/after patch) and dropping into shell ..."
echo ""
# Use -it only when attached to a real TTY (interactive terminal).
# When piped/non-interactive, omit -t so docker doesn't error.
if [ -t 0 ] && [ -t 1 ]; then
    TTY_FLAGS="-it"
else
    TTY_FLAGS="-i"
fi
docker run --rm $TTY_FLAGS \
    -e TERM="${TERM:-xterm-256color}" \
    "$IMAGE_TAG"
