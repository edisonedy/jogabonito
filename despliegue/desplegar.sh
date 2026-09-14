#!/usr/bin/env bash
#
# Despliegue de Joga Bonito en el servidor (Ubuntu/Debian con Nginx).
#
#   La PRIMERA vez:   sudo bash desplegar.sh --primera-vez
#   Cada actualizada: sudo bash desplegar.sh
#
# Lo que hace cada vez: baja el codigo nuevo, instala lo que falte, aplica
# migraciones, junta los estaticos y reinicia el servicio. No toca la base de
# datos mas alla de las migraciones, y nunca toca el .env.
#
set -euo pipefail

APP=jogabonito
RUTA=/opt/$APP
USUARIO=$APP
RAMA=main

verde() { printf '\n\033[1;32m==> %s\033[0m\n' "$1"; }
rojo()  { printf '\n\033[1;31m!!! %s\033[0m\n' "$1" >&2; }

if [ "$(id -u)" -ne 0 ]; then
  rojo "Hay que correrlo con sudo."
  exit 1
fi

# ---------------------------------------------------------------- primera vez
if [ "${1:-}" = "--primera-vez" ]; then
  verde "Instalando lo que necesita el servidor"
  apt-get update
  apt-get install -y python3-venv python3-pip postgresql nginx git

  verde "Creando el usuario del sistema y la carpeta"
  id -u "$USUARIO" >/dev/null 2>&1 || adduser --system --group --home "$RUTA" "$USUARIO"
  mkdir -p "$RUTA"

  if [ ! -d "$RUTA/.git" ]; then
    rojo "Falta clonar el proyecto:"
    echo "  git clone https://github.com/edisonedy/jogabonito.git $RUTA"
    echo "  cp $RUTA/.env.example $RUTA/.env   # y editarlo"
    exit 1
  fi

  if [ ! -f "$RUTA/.env" ]; then
    rojo "Falta el archivo .env (copialo de .env.example y editalo)."
    exit 1
  fi

  verde "Armando el entorno de Python"
  python3 -m venv "$RUTA/.venv"

  verde "Dejando el servicio y el sitio de Nginx"
  cp "$RUTA/despliegue/jogabonito.service" /etc/systemd/system/
  cp "$RUTA/despliegue/jogabonito.nginx" /etc/nginx/sites-available/$APP
  ln -sf /etc/nginx/sites-available/$APP /etc/nginx/sites-enabled/$APP
  rm -f /etc/nginx/sites-enabled/default
  systemctl daemon-reload
  systemctl enable $APP
fi

# ---------------------------------------------------------------- cada vez
cd "$RUTA"

verde "Bajando el codigo nuevo"
git fetch --all
git checkout "$RAMA"
git pull origin "$RAMA"

verde "Instalando dependencias"
"$RUTA/.venv/bin/pip" install --upgrade pip
"$RUTA/.venv/bin/pip" install -r requirements.txt
"$RUTA/.venv/bin/pip" install gunicorn

verde "Revisando que el proyecto este sano"
"$RUTA/.venv/bin/python" manage.py check --deploy

verde "Aplicando migraciones"
"$RUTA/.venv/bin/python" manage.py migrate --noinput

verde "Juntando los archivos estaticos"
"$RUTA/.venv/bin/python" manage.py collectstatic --noinput

# La base del sistema (modulos, permisos, catalogos) es idempotente: se puede
# correr siempre. NO se toca la clave del administrador si ya existe.
verde "Actualizando modulos y catalogos"
"$RUTA/.venv/bin/python" manage.py cargar_base

verde "Abriendo las mensualidades que hayan vencido"
"$RUTA/.venv/bin/python" manage.py poner_al_dia

verde "Dejando los permisos en orden"
chown -R "$USUARIO:$USUARIO" "$RUTA"
chmod 640 "$RUTA/.env"

verde "Reiniciando"
systemctl restart $APP
nginx -t && systemctl reload nginx

sleep 2
systemctl --no-pager --lines=5 status $APP || true

verde "Listo. Revisa el sitio en el navegador."
