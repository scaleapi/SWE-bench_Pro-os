FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

COPY install_system_deps.sh /install_system_deps.sh
RUN bash /install_system_deps.sh

# ADD scripts /scripts
# ADD run_scripts /run_scripts