# Poner Joga Bonito en un servidor

Django + Gunicorn + Nginx + PostgreSQL, en un Ubuntu o Debian.
Todo se hace una sola vez; despues cada actualizada es **un solo comando**.

## 1. La primera vez

```bash
# 1. Traer el codigo
sudo mkdir -p /opt/jogabonito
sudo git clone https://github.com/edisonedy/jogabonito.git /opt/jogabonito
cd /opt/jogabonito

# 2. La base de datos
sudo -u postgres psql -c "CREATE DATABASE jogabonito;"
sudo -u postgres psql -c "CREATE USER jogabonito WITH PASSWORD 'una-clave-larga';"
sudo -u postgres psql -c "ALTER DATABASE jogabonito OWNER TO jogabonito;"

# 3. La configuracion (NUNCA se sube al repositorio)
sudo cp .env.example .env
sudo nano .env
```

En el `.env` de produccion hay que cambiar **sin falta**:

```ini
DJANGO_SECRET_KEY=<una clave larga y al azar>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=jogabonito.horus-tecnologia.com

DB_NAME=jogabonito
DB_USER=jogabonito
DB_PASSWORD=<la clave que pusiste arriba>
DB_HOST=localhost
DB_PORT=5432
```

Para sacar una clave secreta:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(60))"
```

Despues:

```bash
sudo bash /opt/jogabonito/despliegue/desplegar.sh --primera-vez
```

Eso instala todo, deja el servicio andando y configura Nginx.

### El administrador

```bash
sudo -u jogabonito /opt/jogabonito/.venv/bin/python /opt/jogabonito/manage.py \
    cargar_base --admin-clave "una-clave-que-no-sea-edison"
```

**La clave `edison` es solo para la computadora de desarrollo.** En el
servidor hay que poner una de verdad.

### El candado (https)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d jogabonito.horus-tecnologia.com
```

Con `DJANGO_DEBUG=False` el sistema ya exige cookies seguras y HSTS, asi que
esto no es opcional: sin https no se puede entrar.

## 2. Cada vez que haya algo nuevo

```bash
sudo bash /opt/jogabonito/despliegue/desplegar.sh
```

Baja el codigo, instala lo que falte, migra, junta los estaticos, actualiza
los modulos, abre las mensualidades vencidas y reinicia. **No toca el `.env`
ni borra datos.**

## 3. Tarea diaria (opcional)

```bash
sudo crontab -u jogabonito /opt/jogabonito/despliegue/tarea-diaria.cron
```

Abre las mensualidades que vencen aunque nadie entre al sistema.

## 4. Respaldo de la base

```bash
sudo -u postgres pg_dump jogabonito | gzip > ~/jogabonito-$(date +%F).sql.gz
```

Vale la pena dejarlo tambien en el cron. **Antes de cada despliegue grande,
saca un respaldo.**

## Cuando algo falla

```bash
sudo systemctl status jogabonito          # como esta el servicio
sudo journalctl -u jogabonito -n 50       # ultimos errores
tail -50 /var/log/jogabonito/error.log    # errores de la aplicacion
sudo nginx -t                             # la configuracion de Nginx
```

## Lo que hay que saber

- El codigo vive en `/opt/jogabonito` y corre con el usuario `jogabonito`.
- Las fotos que se suben quedan en `/opt/jogabonito/media/`: **eso no esta en
  el repositorio**, hay que respaldarlo aparte.
- Los estaticos se arman en `/opt/jogabonito/staticfiles/` y los sirve Nginx.
- El `.env` es el unico archivo con claves y nunca se sube a GitHub.
