# coding=utf-8
"""Vistas comunes: login, panel de modulos, mi cuenta y cambio de clave."""
from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render

from jogabonito.decorators import URL_LOGIN, URL_PANEL, last_access, modulos_del_usuario, path_modulo
from jogabonito.forms import CambiarClaveForm
from jogabonito.funciones import bad_json, ok_json
from jogabonito.models import Modulo, PerfilUsuario


def ip_cliente(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def perfil_de(usuario):
    """Perfil del usuario; se crea al vuelo para el superusuario."""
    perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
    if not perfil and usuario.is_superuser:
        from jogabonito.models import ROL_ADMINISTRADOR
        perfil = PerfilUsuario(usuario=usuario, rol=ROL_ADMINISTRADOR)
        perfil.save()
    return perfil


def adduserdata(request, data):
    """Carga en `data` lo que necesitan la base y el sidebar."""
    usuario = request.user
    perfil = perfil_de(usuario)
    if perfil is None or not perfil.activo:
        raise PermissionError('El usuario no tiene un perfil activo en el sistema.')

    data['usuario'] = usuario
    data['perfil'] = perfil
    data['entrenador'] = perfil.entrenador()
    data['es_administrador'] = perfil.es_administrador()
    data['es_entrenador'] = perfil.es_entrenador()
    data['currenttime'] = datetime.now()
    data['remoteaddr'] = ip_cliente(request)
    data['mismodulos'] = modulos_del_usuario(usuario).order_by('orden', 'nombre')

    # Migas de pan: Inicio + el modulo actual.
    url_modulo = path_modulo(request)
    ruta = [[URL_PANEL, 'Inicio']]
    if url_modulo:
        modulo = Modulo.objects.filter(url=url_modulo).first()
        if modulo:
            ruta.append([URL_PANEL + modulo.url, modulo.nombre])
            data['modulo_actual'] = modulo
    data['ruta'] = ruta
    return data


@transaction.atomic()
def login_user(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(URL_PANEL)

    data = {'title': 'Ingreso al sistema'}

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip().lower()
        password = request.POST.get('password') or ''
        usuario = authenticate(request, username=username, password=password)

        if usuario is None or not usuario.is_active:
            data['error'] = 'Usuario o clave incorrectos.'
            return render(request, 'login.html', data)

        perfil = perfil_de(usuario)
        if perfil is None or not perfil.activo:
            data['error'] = 'El usuario no tiene acceso al sistema. Contacte al administrador.'
            return render(request, 'login.html', data)

        login(request, usuario)
        request.session['ultimo_acceso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return HttpResponseRedirect(URL_PANEL)

    return render(request, 'login.html', data)


def logout_user(request):
    logout(request)
    return HttpResponseRedirect(URL_LOGIN)


@login_required(login_url=URL_LOGIN)
@last_access
def panel(request):
    data = {'title': 'Panel principal'}
    try:
        adduserdata(request, data)
    except PermissionError:
        logout(request)
        return HttpResponseRedirect(URL_LOGIN)
    return render(request, 'panel.html', data)


@login_required(login_url=URL_LOGIN)
def micuenta(request):
    data = {'title': 'Mi cuenta'}
    try:
        adduserdata(request, data)
    except PermissionError:
        logout(request)
        return HttpResponseRedirect(URL_LOGIN)
    return render(request, 'micuenta.html', data)


@login_required(login_url=URL_LOGIN)
@transaction.atomic()
def passwd(request):
    """Cambio de clave del propio usuario (nunca de otro)."""
    if request.method == 'POST':
        if request.POST.get('action') != 'cambiarclave':
            return bad_json(error=0)
        form = CambiarClaveForm(request.POST, usuario=request.user)
        if not form.is_valid():
            primer_error = next(iter(form.errors.values()))[0]
            return bad_json(mensaje=primer_error)
        request.user.set_password(form.cleaned_data['clave_nueva'])
        request.user.save()
        return ok_json({'mensaje': 'Clave actualizada. Vuelva a ingresar al sistema.',
                        'redirect_url': URL_LOGIN})

    data = {'title': 'Cambiar clave', 'form': CambiarClaveForm(usuario=request.user)}
    return render(request, 'changepass.html', data)
