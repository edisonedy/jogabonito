# coding=utf-8
"""Datos de la academia disponibles en todas las plantillas."""
import os

from django.conf import settings

# Nombres que se buscan en static/images/ para usar como logo.
POSIBLES_LOGOS = ('logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp')


def _logo():
    """Ruta estatica del logo si el archivo existe; si no None (se dibuja el balon)."""
    for carpeta in settings.STATICFILES_DIRS:
        for nombre in POSIBLES_LOGOS:
            if os.path.exists(os.path.join(carpeta, 'images', nombre)):
                return 'images/%s' % nombre
    return None


def _whatsapp(numero):
    """09XXXXXXXX -> 5939XXXXXXXX para los enlaces wa.me."""
    digitos = ''.join(c for c in (numero or '') if c.isdigit())
    if digitos.startswith('0'):
        digitos = '593' + digitos[1:]
    return digitos


def academia(request):
    whatsapp = settings.ACADEMIA_WHATSAPP or settings.ACADEMIA_TELEFONO
    return {
        'academia': {
            'nombre': settings.ACADEMIA_NOMBRE,
            'lema': settings.ACADEMIA_LEMA,
            'descripcion': settings.ACADEMIA_DESCRIPCION,
            'direccion': settings.ACADEMIA_DIRECCION,
            'telefono': settings.ACADEMIA_TELEFONO,
            'whatsapp': whatsapp,
            'whatsapp_link': _whatsapp(whatsapp),
            'email': settings.ACADEMIA_EMAIL,
            'logo': _logo(),
            'director': settings.ACADEMIA_DIRECTOR,
            'director_cargo': settings.ACADEMIA_DIRECTOR_CARGO,
            'director_bio': settings.ACADEMIA_DIRECTOR_BIO,
            'director_foto': settings.ACADEMIA_DIRECTOR_FOTO,
            'instagram': settings.ACADEMIA_INSTAGRAM,
            'facebook': settings.ACADEMIA_FACEBOOK,
            'tiktok': settings.ACADEMIA_TIKTOK,
            'mapa_embed': settings.ACADEMIA_MAPA_EMBED,
            'mapa_link': settings.ACADEMIA_MAPA_LINK,
        }
    }
