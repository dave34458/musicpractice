#!/usr/bin/env bash
# MusicPractice GCP deploy script. Run as root on the VM.
#   sudo bash deploy.sh bootstrap   -> system deps + NVIDIA driver, then REBOOT
#   sudo bash deploy.sh app         -> venv, repo, env, migrate, services
set -euo pipefail

APP_USER=musicpractice
APP_DIR=/home/$APP_USER/musicpractice
DATA_DIR=/home/$APP_USER/data
VENV=/home/$APP_USER/venv
REPO=https://github.com/dave34458/musicpractice.git

bootstrap() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3.12-venv python3-pip ffmpeg nginx curl unzip ca-certificates git openssl
    curl -fsSL -o /tmp/deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip
    unzip -o /tmp/deno.zip -d /usr/local/bin/
    apt-get install -y linux-headers-$(uname -r)
    apt-get install -y nvidia-driver-550
    echo "=== Reboot required. Run: sudo reboot  (then)  sudo bash deploy.sh app ==="
}

app() {
    id $APP_USER 2>/dev/null || useradd -m -s /bin/bash $APP_USER
    mkdir -p $DATA_DIR/media $DATA_DIR/logs
    chown -R $APP_USER:$APP_USER $DATA_DIR

    if [ ! -d $APP_DIR/.git ]; then
        sudo -u $APP_USER git clone $REPO $APP_DIR
    else
        sudo -u $APP_USER git -C $APP_DIR pull --ff-only
    fi
    chown -R $APP_USER:$APP_USER $APP_DIR

    [ -x $VENV/bin/python ] || sudo -u $APP_USER python3 -m venv $VENV
    sudo -u $APP_USER $VENV/bin/pip install --upgrade pip
    sudo -u $APP_USER $VENV/bin/pip install torch --index-url https://download.pytorch.org/whl/cu124
    sudo -u $APP_USER $VENV/bin/pip install -r $APP_DIR/requirements.txt

    if [ ! -f /home/$APP_USER/musicpractice.env ]; then
        IP=$(curl -fsSL -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
        umask 077
        cat > /home/$APP_USER/musicpractice.env <<EOF
DJANGO_SECRET_KEY=$(openssl rand -hex 25)
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=$IP
DJANGO_CSRF_TRUSTED_ORIGINS=http://$IP
DATA_DIR=$DATA_DIR
MUSCRIPTOR_MODEL_PATH=$APP_DIR/models/muscriptor-small.safetensors
EOF
        chown $APP_USER:$APP_USER /home/$APP_USER/musicpractice.env
    fi

    sudo -u $APP_USER bash -c "cd $APP_DIR && $VENV/bin/python manage.py migrate --noinput"
    sudo -u $APP_USER bash -c "cd $APP_DIR && $VENV/bin/python manage.py collectstatic --noinput"

    cp $APP_DIR/deploy/musicpractice.service /etc/systemd/system/
    cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/musicpractice
    ln -sf /etc/nginx/sites-available/musicpractice /etc/nginx/sites-enabled/musicpractice
    rm -f /etc/nginx/sites-enabled/default
    systemctl daemon-reload
    systemctl enable --now musicpractice
    systemctl restart nginx

    echo "=== nvidia ==="
    nvidia-smi | head -5 || true
    sudo -u $APP_USER $VENV/bin/python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
    echo "=== site ==="
    curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://localhost/ || true
}
