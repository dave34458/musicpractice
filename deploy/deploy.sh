#!/bin/bash
set -e
REPO=/home/musicpractice/musicpractice
VENV=/home/musicpractice/data/venv
ENVF=/home/musicpractice/data/musicpractice.env

sudo -u musicpractice git -C "$REPO" pull --ff-only
sudo cp "$REPO/deploy/nginx.conf" /etc/nginx/sites-available/musicpractice
sudo nginx -t
sudo systemctl reload nginx

sudo -u musicpractice bash -c "
set -a
. $ENVF
set +a
export MIDIS_NO_WORKER=1
cd $REPO
$VENV/bin/python manage.py migrate --noinput
$VENV/bin/python manage.py collectstatic --noinput
"

sudo systemctl restart musicpractice
