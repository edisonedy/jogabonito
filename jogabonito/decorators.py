# coding=utf-8
"""Decoradores de seguridad del sistema.

`secure_module` valida que el usuario tenga asignado el modulo que esta
abriendo, usando el primer segmento de la URL (igual que jdsistemas).
"""
from datetime import datetime
from functools import wraps

from django.http import HttpResponseRedirect

from jogabonito.funciones import bad_json
from jogabonito.models import Modulo

URL_PANEL = '/sistema/'
URL_LOGIN = '/sistema/login/'


def path_modulo(request):
    """'/sistema/adm_jugador?id=3' -> 'adm_jugador'."""
    path = (request.path or '/').strip('/')
    if path.startswith('sistema'):
        path = path[len('sistema'):].strip('/')
    if not path:
        return ''
    return path.split('/')[0]


def modulos_del_usuario(usuario):
    """Modulos activos asignados a los grupos del usuario."""
    if not usuario.is_authenticated:
        return Modulo.objects.none()
    if usuario.is_superuser:
        return Modulo.objects.filter(activo=True)
    return Modulo.objects.filter(
        activo=True,
        gruposmodulos__grupo__in=usuario.groups.all()
    ).distinct()


def puede_entrar(usuario, url_modulo):
    if not url_modulo:
        return True
    return modulos_del_usuario(usuario).filter(url=url_modulo).exists()


def rechazar_acceso(request):
    """AJAX recibe JSON; una navegacion normal vuelve al panel."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return bad_json(error=4)
    return HttpResponseRedirect(URL_PANEL)


def secure_module(f):
    @wraps(f)
    def nueva(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(URL_LOGIN)
        if not puede_entrar(request.user, path_modulo(request)):
            return rechazar_acceso(request)
        return f(request, *args, **kwargs)

    return nueva


def solo_administrador(f):
    """Bloquea el modulo a cualquiera que no sea administrador."""

    @wraps(f)
    def nueva(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(URL_LOGIN)
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.es_administrador())):
            return rechazar_acceso(request)
        return f(request, *args, **kwargs)

    return nueva


def last_access(f):
    """Guarda en la sesion la hora del ultimo modulo abierto."""

    @wraps(f)
    def nueva(request, *args, **kwargs):
        request.session['ultimo_acceso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f(request, *args, **kwargs)

    return nueva
