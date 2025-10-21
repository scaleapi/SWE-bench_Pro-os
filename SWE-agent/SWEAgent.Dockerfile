# SWE Agent Dockerfile
# This Dockerfile sets up the SWE Agent environment with all necessary dependencies
# and installs the required swerex patch.
FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install -e .

# Install swerex patch from forked repo at the head of the sweap_support branch (base version v1.2.0)
RUN git clone -b sweap_support --single-branch https://github.com/mayavkrishnan25/SWE-ReX.git /SWE-ReX
WORKDIR /SWE-ReX
RUN pip install -e .


# Install swebench harness forked repo at the head of modal_support branch (base version v2.0.13) 
RUN git clone -b modal_support --single-branch https://github.com/mayavkrishnan25/SWE-bench.git /SWE-bench
WORKDIR /SWE-bench
RUN pip install -e .


WORKDIR /app

CMD ["/bin/bash"]