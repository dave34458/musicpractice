#!/usr/bin/env bash
# MusicPractice GCP auto-provisioner. Idempotent — safe to run on every boot.
# Runs via startup-script on first boot and after spot preemption re-creates.
set -euo pipefail

APP_USER=musicpractice
HOME_DIR=/home/$APP_USER
DATA_DIR=$HOME_DIR/data
DATA_DEV=/dev/disk/by-id/google-musicpractice-data
VENV=$DATA_DIR/venv
REPO=$HOME_DIR/musicpractice
GIT=https://github.com/dave34458/musicpractice.git

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# ---- user + data disk: format once, mount, persist in fstab ----
id $APP_USER 2>/dev/null || useradd -m -s /bin/bash $APP_USER
mkdir -p $HOME_DIR $DATA_DIR
chown -R $APP_USER:$APP_USER $HOME_DIR
if ! mountpoint -q $DATA_DIR; then
    if ! blkid $DATA_DEV >/dev/null 2>&1; then
        mkfs.ext4 -F $DATA_DEV
    fi
    mount $DATA_DEV $DATA_DIR
    UUID=$(blkid -s UUID -o value $DATA_DEV)
    grep -q "$UUID" /etc/fstab || echo "UUID=$UUID $DATA_DIR ext4 defaults,nofail 0 2" >> /etc/fstab
fi

# ---- repo (fresh boot disk -> clone each time; LFS weights stay on data disk) ----
[ -d $REPO/.git ] || sudo -u $APP_USER git clone $GIT $REPO
chown -R $APP_USER:$APP_USER $HOME_DIR

# ---- NVIDIA driver: once per data-disk lifetime, then reboot ----
if ! nvidia-smi >/dev/null 2>&1 && [ ! -f $DATA_DIR/.driver ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y linux-headers-$(uname -r)
    apt-get install -y nvidia-driver-550
    touch $DATA_DIR/.driver
    log "driver installed; rebooting"
    reboot
fi

# ---- system deps ----
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3.12-venv python3-pip ffmpeg nginx curl unzip ca-certificates git openssl
if ! command -v deno >/dev/null 2>&1; then
    curl -fsSL -o /tmp/deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip
    unzip -o /tmp/deno.zip -d /usr/local/bin/
fi

# ---- env (on data disk so it survives preemption) ----
if [ ! -f $DATA_DIR/musicpractice.env ]; then
    IP=$(curl -fsSL -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
    umask 077
    cat > $DATA_DIR/musicpractice.env <<EOF
DJANGO_SECRET_KEY=$(openssl rand -hex 25)
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=$IP
DJANGO_CSRF_TRUSTED_ORIGINS=http://$IP
DATA_DIR=$DATA_DIR
MUSCRIPTOR_MODEL_PATH=$DATA_DIR/models/muscriptor-small.safetensors
EOF
    chown $APP_USER:$APP_USER $DATA_DIR/musicpractice.env
fi

# ---- venv + python deps ----
[ -x $VENV/bin/python ] || sudo -u $APP_USER python3 -m venv $VENV
sudo -u $APP_USER $VENV/bin/pip install --upgrade pip
sudo -u $APP_USER $VENV/bin/pip install torch --index-url https://download.pytorch.org/whl/cu124
sudo -u $APP_USER $VENV/bin/pip install -r $REPO/requirements.txt

# ---- django ----
sudo -u $APP_USER bash -c "set -a; . $DATA_DIR/musicpractice.env; set +a; cd $REPO && $VENV/bin/python manage.py migrate --noinput"
sudo -u $APP_USER bash -c "cd $REPO && $VENV/bin/python manage.py collectstatic --noinput"

# ---- services ----
cp $REPO/deploy/musicpractice.service /etc/systemd/system/
cp $REPO/deploy/nginx.conf /etc/nginx/sites-available/musicpractice
ln -sf /etc/nginx/sites-available/musicpractice /etc/nginx/sites-enabled/musicpractice
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
systemctl enable --now musicpractice
systemctl restart nginx

log "=== GPU ==="
nvidia-smi | head -5 || true
sudo -u $APP_USER $VENV/bin/python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
curl -fsS -o /dev/null -w "site: HTTP %{http_code}\n" http://localhost/ || true
