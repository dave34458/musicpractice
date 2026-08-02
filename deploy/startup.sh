#!/bin/bash
# Startup script for the MIG instance template. Runs on every boot.
# Clones the repo (provisioner lives there) then runs it idempotently.
exec >/var/log/musicpractice-startup.log 2>&1
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git ca-certificates curl
if [ ! -d /opt/musicpractice/.git ]; then
    rm -rf /opt/musicpractice
    git clone https://github.com/dave34458/musicpractice.git /opt/musicpractice
fi
bash /opt/musicpractice/deploy/provision.sh
