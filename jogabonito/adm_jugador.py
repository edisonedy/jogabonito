# coding=utf-8
"""Modulo: jugadores.

El administrador administra todo. El entrenador SOLO consulta los jugadores
de las categorias que tiene asignadas (el filtro se aplica en el queryset,
nunca se confia en el id que llega del navegador).
"""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.acceso import categorias_permitidas, jugadores_permitidos
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.forms import JugadorForm
from jogabonito.funciones import bad_json, generar_nombre, ok_json, paginar, url_back
from jogabonito.models import ESTADOS_JUGADOR, JUGADOR_ACTIVO, Jugador

MODULO = 'adm_jugador'


def _primer_error(form):
    return next(iter(form.errors.values()))[0]


@login_required(login_url=URL_LOGIN)
@secure_module
@last_access
@transaction.atomic()
def view(request):
    data = {}
    perfil = perfil_de(request.user)
    if perfil is None or not perfil.activo:
        return bad_json(error=4) if request.method == 'POST' else url_back(request)

    if request.method == 'POST':
        # Todas las escrituras son exclusivas del administrador.
        if not perfil.es_administrador():
            return bad_json(error=4)

        action = request.POST.get('action')

        if action == 'add':
            try:
                form = JugadorForm(request.POST, request.FILES)
                if not form.is_valid():
                    return bad_json(mensaje=_primer_error(form))
                jugador = form.save(commit=False)
                if jugador.fotografia:
                    jugador.fotografia.name = generar_nombre('jugador_', jugador.fotografia.name)
                jugador.save(request)
                return ok_json({'mensaje': 'Jugador registrado.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'edit':
            try:
                jugador = Jugador.objects.get(pk=int(request.POST['id']))
                form = JugadorForm(request.POST, request.FILES, instance=jugador)
                if not form.is_valid():
                    return bad_json(mensaje=_primer_error(form))
                jugador = form.save(commit=False)
                if 'fotografia' in request.FILES:
                    jugador.fotografia.name = generar_nombre('jugador_', jugador.fotografia.name)
                jugador.save(request)
                return ok_json({'mensaje': 'Jugador actualizado.'})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                jugador = Jugador.objects.get(pk=int(request.POST['id']))
                jugador.delete()
                return ok_json({'mensaje': 'Jugador eliminado.'})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        if action == 'estado':
            try:
                jugador = Jugador.objects.get(pk=int(request.POST['id']))
                estado = int(request.POST.get('estado', 0))
                if estado not in dict(ESTADOS_JUGADOR):
                    return bad_json(error=6)
                jugador.estado = estado
                jugador.save(request)
                return ok_json({'mensaje': 'Estado actualizado.'})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except (TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    permitidos = jugadores_permitidos(perfil)
    action = request.GET.get('action')
    solo_lectura = not perfil.es_administrador()
    data['solo_lectura'] = solo_lectura

    if action in ('add', 'edit', 'delete') and solo_lectura:
        return url_back(request)

    if action == 'add':
        data['title'] = 'Nuevo jugador'
        data['form'] = JugadorForm()
        return render(request, 'adm_jugador/add.html', data)

    if action == 'edit':
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Editar jugador'
        data['jugador'] = jugador
        data['form'] = JugadorForm(instance=jugador)
        return render(request, 'adm_jugador/edit.html', data)

    if action == 'delete':
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Eliminar jugador'
        data['jugador'] = jugador
        return render(request, 'adm_jugador/delete.html', data)

    if action == 'view':
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Ficha del jugador'
        data['jugador'] = jugador
        data['entrenadores'] = jugador.entrenadores()
        data['resumen'] = jugador.resumen_asistencia()
        data['asistencias'] = jugador.ultimas_asistencias(10)
        return render(request, 'adm_jugador/ficha.html', data)

    data['title'] = 'Jugadores'
    buscar = (request.GET.get('s') or '').strip()
    jugadores = permitidos

    if buscar:
        jugadores = jugadores.filter(
            Q(nombres__icontains=buscar) | Q(apellidos__icontains=buscar) |
            Q(cedula__icontains=buscar) | Q(telefono__icontains=buscar)
        )

    categoria_id = request.GET.get('categoria')
    if categoria_id:
        try:
            jugadores = jugadores.filter(categoria_id=int(categoria_id))
            data['categoria_id'] = int(categoria_id)
        except (TypeError, ValueError):
            pass

    estado = request.GET.get('estado')
    if estado:
        try:
            jugadores = jugadores.filter(estado=int(estado))
            data['estado_id'] = int(estado)
        except (TypeError, ValueError):
            pass

    data['search'] = buscar
    data['categorias'] = categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio')
    data['estados'] = ESTADOS_JUGADOR
    data['total_jugadores'] = permitidos.filter(estado=JUGADOR_ACTIVO).count()
    data['jugadores'] = paginar(request, jugadores, data, MODULO)
    return render(request, 'adm_jugador/view.html', data)
