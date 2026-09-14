"""
Configuracion del sistema de gestion de la Academia Joga Bonito.

Mismo esquema que jdsistemas: el paquete del proyecto es tambien la app principal,
por lo que aqui viven settings, models, forms y los modulos adm_*.py.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env(clave, defecto=''):
    valor = os.getenv(clave)
    return valor if valor not in (None, '') else defecto


def env_bool(clave, defecto=False):
    valor = os.getenv(clave)
    if valor is None:
        return defecto
    return valor.strip().lower() in ('1', 'true', 'yes', 'on', 'si')


SECRET_KEY = env('DJANGO_SECRET_KEY', 'django-insecure-cambiar-en-produccion-jogabonito')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = [x.strip() for x in env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in env('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'jogabonito',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'jogabonito.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'jogabonito.context_processors.academia',
            ],
        },
    },
]

WSGI_APPLICATION = 'jogabonito.wsgi.application'
ASGI_APPLICATION = 'jogabonito.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', 'jogabonito'),
        'USER': env('DB_USER', 'postgres'),
        'PASSWORD': env('DB_PASSWORD', 'postgres'),
        'HOST': env('DB_HOST', 'localhost'),
        'PORT': env('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = False

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/sistema/login/'
LOGIN_REDIRECT_URL = '/sistema/'
LOGOUT_REDIRECT_URL = '/sistema/login/'

# --- Sesion y seguridad -------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', False)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --- Datos de la academia (una sola academia en esta etapa) -------------
ACADEMIA_NOMBRE = env('ACADEMIA_NOMBRE', 'Academia Joga Bonito')
ACADEMIA_LEMA = env('ACADEMIA_LEMA', 'Formacion futbolistica con alegria')
ACADEMIA_DIRECCION = env('ACADEMIA_DIRECCION', 'Ambato - Ecuador')
ACADEMIA_TELEFONO = env('ACADEMIA_TELEFONO', '')
ACADEMIA_WHATSAPP = env('ACADEMIA_WHATSAPP', '')
ACADEMIA_EMAIL = env('ACADEMIA_EMAIL', '')
ACADEMIA_DESCRIPCION = env(
    'ACADEMIA_DESCRIPCION',
    'Formamos futbolistas dentro y fuera de la cancha. Trabajamos la tecnica, la tactica '
    'y sobre todo el gusto por jugar bien: el joga bonito.'
)
# Anios de trayectoria (solo el numero, sin fechas). Vacio = no se muestra.
ACADEMIA_ANIOS = env('ACADEMIA_ANIOS', '2')

# Responsable de la academia (seccion "Quien dirige" de la pagina publica).
ACADEMIA_DIRECTOR = env('ACADEMIA_DIRECTOR', 'Kevin Supe')
ACADEMIA_DIRECTOR_CARGO = env('ACADEMIA_DIRECTOR_CARGO', 'Director y entrenador de la academia')
ACADEMIA_DIRECTOR_BIO = env('ACADEMIA_DIRECTOR_BIO', '')
ACADEMIA_DIRECTOR_FOTO = env('ACADEMIA_DIRECTOR_FOTO', '')

# Redes y ubicacion. Si quedan vacias, esa parte de la pagina no se dibuja.
ACADEMIA_INSTAGRAM = env('ACADEMIA_INSTAGRAM', '')
ACADEMIA_FACEBOOK = env('ACADEMIA_FACEBOOK', '')
ACADEMIA_TIKTOK = env('ACADEMIA_TIKTOK', '')
ACADEMIA_MAPA_EMBED = env(
    'ACADEMIA_MAPA_EMBED',
    'https://www.google.com/maps?q=-1.263422,-78.568008&hl=es&z=17&output=embed'
)
ACADEMIA_MAPA_LINK = env('ACADEMIA_MAPA_LINK', 'https://maps.app.goo.gl/7WQef3g5AcpoCVY4A')

# Tope de solicitudes que acepta la landing desde una misma IP por hora.
SOLICITUDES_MAXIMAS_POR_HORA = int(env('SOLICITUDES_MAXIMAS_POR_HORA', '5'))

# --- Quien desarrolla el sistema (credito en la landing y en el sistema) ---
# Si DESARROLLADOR_NOMBRE queda vacio, el credito no se dibuja en ningun lado.
DESARROLLADOR_NOMBRE = env('DESARROLLADOR_NOMBRE', 'HORUS')
DESARROLLADOR_LEMA = env('DESARROLLADOR_LEMA', 'Soluciones Tecnologicas')
DESARROLLADOR_URL = env('DESARROLLADOR_URL', '')
DESARROLLADOR_WHATSAPP = env('DESARROLLADOR_WHATSAPP', '0999955936')
DESARROLLADOR_EMAIL = env('DESARROLLADOR_EMAIL', 'edisonmoyolema@hotmail.com')
DESARROLLADOR_COLOR = env('DESARROLLADOR_COLOR', '#009FE3')

# --- Grupos del sistema --------------------------------------------------
GRUPO_ADMINISTRADOR = 'ADMINISTRADOR'
GRUPO_ENTRENADOR = 'ENTRENADOR'

# --- Subida de imagenes --------------------------------------------------
IMAGEN_EXTENSIONES_PERMITIDAS = ['jpg', 'jpeg', 'png', 'webp']
IMAGEN_TAMANO_MAXIMO = 3 * 1024 * 1024
