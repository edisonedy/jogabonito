# coding=utf-8
"""Datos de la academia disponibles en todas las plantillas."""
import os

from django.conf import settings
from django.templatetags.static import static as ruta_estatica

from jogabonito.models import numero_para_whatsapp

# Nombres que se buscan en static/images/ para usar como logo.
POSIBLES_LOGOS = ('logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp', 'logo.svg')
POSIBLES_LOGOS_HORUS = ('horus.svg', 'horus.png', 'horus.jpg', 'horus.webp')
POSIBLES_DIRECTOR = ('director.jpg', 'director.jpeg', 'director.png', 'director.webp')


def buscar_imagen(nombres):
    """Ruta estatica de la primera imagen que exista, o None."""
    for carpeta in settings.STATICFILES_DIRS:
        for nombre in nombres:
            if os.path.exists(os.path.join(carpeta, 'images', nombre)):
                return 'images/%s' % nombre
    return None


def logo_academia():
    """Logo de la academia; si no esta el archivo, la plantilla dibuja el escudo."""
    return buscar_imagen(POSIBLES_LOGOS)


def foto_director():
    """La foto del director: manda la del .env y si no, la de static/images."""
    puesta_a_mano = settings.ACADEMIA_DIRECTOR_FOTO
    if puesta_a_mano:
        if puesta_a_mano.startswith(('http://', 'https://', '/')):
            return puesta_a_mano
        return ruta_estatica(puesta_a_mano)

    encontrada = buscar_imagen(POSIBLES_DIRECTOR)
    return ruta_estatica(encontrada) if encontrada else ''


def fotos_galeria(maximo=8):
    """Fotos de static/images/galeria/. Si la carpeta esta vacia, no hay galeria."""
    extensiones = ('.jpg', '.jpeg', '.png', '.webp')
    for carpeta in settings.STATICFILES_DIRS:
        ruta = os.path.join(carpeta, 'images', 'galeria')
        if not os.path.isdir(ruta):
            continue
        nombres = sorted(
            n for n in os.listdir(ruta) if n.lower().endswith(extensiones)
        )
        return ['images/galeria/%s' % n for n in nombres[:maximo]]
    return []


def academia(request):
    whatsapp = settings.ACADEMIA_WHATSAPP or settings.ACADEMIA_TELEFONO
    return {
        'desarrollador': {
            'nombre': settings.DESARROLLADOR_NOMBRE,
            'lema': settings.DESARROLLADOR_LEMA,
            'url': settings.DESARROLLADOR_URL,
            'whatsapp': settings.DESARROLLADOR_WHATSAPP,
            'whatsapp_link': numero_para_whatsapp(settings.DESARROLLADOR_WHATSAPP),
            'email': settings.DESARROLLADOR_EMAIL,
            'color': settings.DESARROLLADOR_COLOR,
            'logo': buscar_imagen(POSIBLES_LOGOS_HORUS),
        },
        'academia': {
            'nombre': settings.ACADEMIA_NOMBRE,
            'lema': settings.ACADEMIA_LEMA,
            'descripcion': settings.ACADEMIA_DESCRIPCION,
            'direccion': settings.ACADEMIA_DIRECCION,
            'telefono': settings.ACADEMIA_TELEFONO,
            'whatsapp': whatsapp,
            'whatsapp_link': numero_para_whatsapp(whatsapp),
            'email': settings.ACADEMIA_EMAIL,
            'logo': logo_academia(),
            'galeria': fotos_galeria(),
            'anios': settings.ACADEMIA_ANIOS,
            'director': settings.ACADEMIA_DIRECTOR,
            'director_cargo': settings.ACADEMIA_DIRECTOR_CARGO,
            'director_bio': settings.ACADEMIA_DIRECTOR_BIO,
            'director_foto': foto_director(),
            'instagram': settings.ACADEMIA_INSTAGRAM,
            'facebook': settings.ACADEMIA_FACEBOOK,
            'tiktok': settings.ACADEMIA_TIKTOK,
            'mapa_embed': settings.ACADEMIA_MAPA_EMBED,
            'mapa_link': settings.ACADEMIA_MAPA_LINK,
        }
    }
