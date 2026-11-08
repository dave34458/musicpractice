#!/bin/bash
# Startup script for the MIG instance template. Runs on every boot.
# Clones the repo (provisioner lives there) then runs it idempotently.
exec >/var/log/musicpractice-startup.log 2>&1
set -e
export DEBIAN_FRONTEND=noninteractive
BRANCH=$(curl -fsSL -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/attributes/musicpractice-branch || echo main)
export MUSICPRACTICE_BRANCH=$BRANCH
apt-get update -y
apt-get install -y git git-lfs ca-certificates curl
git lfs install --system
if [ ! -d /opt/musicpractice/.git ]; then
    rm -rf /opt/musicpractice
    git clone --branch "$BRANCH" https://github.com/dave34458/musicpractice.git /opt/musicpractice
fi
git -C /opt/musicpractice lfs pull
bash /opt/musicpractice/deploy/provision.sh
