# coding=utf-8
"""Modulo: registro de asistencia (FASE 2).

Pensado para el telefono: el entrenador elige grupo y fecha, y marca con un
toque. Cada toque es un POST pequeno que responde JSON, sin recargar la pagina.

El administrador trabaja con toda la academia; el entrenador solo con las
categorias que tiene asignadas (el filtro se aplica en el queryset).
"""
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render

from jogabonito.acceso import (
    categoria_permitida, categorias_permitidas, jugadores_activos_de, jugadores_permitidos,
)
from jogabonito.adm_turno import grupos_de_hoy
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.forms import AsistenciaDetalleForm
from jogabonito.funciones import bad_json, convertir_fecha, ok_json, paginar, url_back
from jogabonito.models import (
    ASISTENCIA_ATRASO, ASISTENCIA_BOTONES, ASISTENCIA_FALTA, ASISTENCIA_JUSTIFICADO,
    ASISTENCIA_PRESENTE, ESTADOS_ASISTENCIA, Asistencia, Jugador, Nota,
)

MODULO = 'adm_asistencia'
ESTADOS_VALIDOS = dict(ESTADOS_ASISTENCIA)


def primer_error(form):
    return next(iter(form.errors.values()))[0]


def fecha_pedida(valor):
    """Convierte la fecha recibida. Devuelve (fecha, error)."""
    if not valor:
        return date.today(), ''
    fecha = convertir_fecha(valor)
    if fecha is None:
        return None, 'La fecha no es valida.'
    if fecha > date.today():
        return None, 'No se puede registrar asistencia de una fecha futura.'
    return fecha, ''


def resumen_del_dia(categoria, fecha):
    """Conteo por estado de una categoria en una fecha."""
    conteo = {estado: 0 for estado, _ in ESTADOS_ASISTENCIA}
    registros = Asistencia.objects.filter(categoria=categoria, fecha=fecha)
    for estado in registros.values_list('estado', flat=True):
        conteo[estado] = conteo.get(estado, 0) + 1

    total_jugadores = jugadores_activos_de(categoria).count()
    marcados = sum(conteo.values())
    return {
        'presentes': conteo[ASISTENCIA_PRESENTE],
        'faltas': conteo[ASISTENCIA_FALTA],
        'atrasos': conteo[ASISTENCIA_ATRASO],
        'justificados': conteo[ASISTENCIA_JUSTIFICADO],
        'marcados': marcados,
        'total': total_jugadores,
        'pendientes': max(total_jugadores - marcados, 0),
    }


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
        action = request.POST.get('action')

        # ---- marcar a un jugador de un toque -------------------------
        if action == 'marcar':
            try:
                categoria = categoria_permitida(perfil, request.POST.get('categoria'))
                if categoria is None:
                    return bad_json(error=4)

                fecha, error = fecha_pedida(request.POST.get('fecha'))
                if error:
                    return bad_json(mensaje=error)

                estado = int(request.POST.get('estado', 0))
                if estado not in ESTADOS_VALIDOS:
                    return bad_json(error=6)

                # El jugador debe pertenecer a esa categoria y estar activo.
                jugador = jugadores_activos_de(categoria).filter(pk=int(request.POST['jugador'])).first()
                if jugador is None:
                    return bad_json(error=4)

                asistencia = Asistencia.objects.filter(
                    jugador=jugador, categoria=categoria, fecha=fecha
                ).first()
                if asistencia is None:
                    asistencia = Asistencia(jugador=jugador, categoria=categoria, fecha=fecha)
                asistencia.estado = estado
                asistencia.save(request)

                return ok_json({
                    'jugador': jugador.id,
                    'estado': estado,
                    'resumen': resumen_del_dia(categoria, fecha),
                })
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- marcar de golpe a los que faltan ------------------------
        if action == 'marcartodos':
            try:
                categoria = categoria_permitida(perfil, request.POST.get('categoria'))
                if categoria is None:
                    return bad_json(error=4)

                fecha, error = fecha_pedida(request.POST.get('fecha'))
                if error:
                    return bad_json(mensaje=error)

                estado = int(request.POST.get('estado', ASISTENCIA_PRESENTE))
                if estado not in ESTADOS_VALIDOS:
                    return bad_json(error=6)

                ya_marcados = set(Asistencia.objects.filter(
                    categoria=categoria, fecha=fecha
                ).values_list('jugador_id', flat=True))

                nuevos = 0
                for jugador in jugadores_activos_de(categoria):
                    if jugador.id in ya_marcados:
                        continue  # nunca pisa lo que el entrenador ya marco
                    Asistencia(jugador=jugador, categoria=categoria, fecha=fecha, estado=estado).save(request)
                    nuevos += 1

                return ok_json({
                    'mensaje': 'Se marcaron %s jugadores.' % nuevos,
                    'recargar': True,
                    'resumen': resumen_del_dia(categoria, fecha),
                })
            except (TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- estado + observacion desde el modal ---------------------
        if action == 'detalle':
            try:
                categoria = categoria_permitida(perfil, request.POST.get('categoria'))
                if categoria is None:
                    return bad_json(error=4)

                fecha, error = fecha_pedida(request.POST.get('fecha'))
                if error:
                    return bad_json(mensaje=error)

                jugador = jugadores_activos_de(categoria).filter(pk=int(request.POST['jugador'])).first()
                if jugador is None:
                    return bad_json(error=4)

                asistencia = Asistencia.objects.filter(
                    jugador=jugador, categoria=categoria, fecha=fecha
                ).first()
                form = AsistenciaDetalleForm(request.POST, instance=asistencia)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                asistencia = form.save(commit=False)
                asistencia.jugador = jugador
                asistencia.categoria = categoria
                asistencia.fecha = fecha
                asistencia.save(request)
                return ok_json({'mensaje': 'Asistencia guardada.'})
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- borrar una marca equivocada -----------------------------
        if action == 'borrar':
            try:
                categoria = categoria_permitida(perfil, request.POST.get('categoria'))
                if categoria is None:
                    return bad_json(error=4)

                fecha, error = fecha_pedida(request.POST.get('fecha'))
                if error:
                    return bad_json(mensaje=error)

                borrados, _ = Asistencia.objects.filter(
                    categoria=categoria, fecha=fecha, jugador_id=int(request.POST['jugador'])
                ).delete()
                if not borrados:
                    return bad_json(error=3)
                return ok_json({'resumen': resumen_del_dia(categoria, fecha)})
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')
    categorias = list(categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio', 'nombre'))
    data['categorias'] = categorias
    data['estados'] = ESTADOS_ASISTENCIA
    data['botones'] = ASISTENCIA_BOTONES

    # ---- modal de estado + observacion -------------------------------
    if action == 'detalle':
        categoria = categoria_permitida(perfil, request.GET.get('categoria'))
        fecha, error = fecha_pedida(request.GET.get('fecha'))
        if categoria is None or error:
            return url_back(request)
        try:
            jugador = jugadores_activos_de(categoria).filter(pk=int(request.GET['jugador'])).first()
        except (KeyError, TypeError, ValueError):
            return url_back(request)
        if jugador is None:
            return url_back(request)

        asistencia = Asistencia.objects.filter(jugador=jugador, categoria=categoria, fecha=fecha).first()
        data['title'] = 'Asistencia de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['categoria'] = categoria
        data['fecha'] = fecha
        data['form'] = AsistenciaDetalleForm(instance=asistencia)
        return render(request, 'adm_asistencia/detalle.html', data)

    # ---- historial de un jugador -------------------------------------
    if action == 'historial':
        try:
            jugador = jugadores_permitidos(perfil).get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        data['title'] = 'Asistencia de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['resumen'] = jugador.resumen_asistencia()
        registros = jugador.asistencias.all().order_by('-fecha')
        data['registros'] = paginar(request, registros, data, MODULO, por_pagina=30)
        return render(request, 'adm_asistencia/historial.html', data)

    # ---- pantalla de marcado -----------------------------------------
    data['title'] = 'Asistencia'
    fecha, error = fecha_pedida(request.GET.get('fecha'))
    if error:
        data['error'] = error
        fecha = date.today()
    data['fecha'] = fecha
    data['fecha_maxima'] = date.today()
    data['fecha_anterior'] = fecha - timedelta(days=1)
    data['fecha_siguiente'] = min(fecha + timedelta(days=1), date.today())

    categoria = None
    if request.GET.get('categoria'):
        categoria = categoria_permitida(perfil, request.GET.get('categoria'))
        if categoria is None:
            return url_back(request)
    else:
        # Sin elegir nada se abre el grupo mas probable: primero el que entrena
        # ese dia, y entre esos el que tenga jugadores. El profe entra y ya
        # tiene la lista lista para marcar, sin elegir nada.
        def prioridad(grupo):
            return (0 if grupo.entrena_hoy(fecha) else 1,
                    0 if grupo.total_jugadores_activos() else 1,
                    grupo.hora_inicio)

        if categorias:
            categoria = sorted(categorias, key=prioridad)[0]

    data['categoria'] = categoria

    # Los grupos que entrenan hoy y estan a su cargo, para verlo donde trabaja.
    yo = perfil.entrenador()
    data['mis_clases'] = [
        grupo for grupo in grupos_de_hoy(categorias, fecha)
        if yo and grupo['encargado'] and grupo['encargado'].id == yo.id
    ]

    if categoria is not None:
        marcas = {
            a.jugador_id: a for a in Asistencia.objects.filter(categoria=categoria, fecha=fecha)
        }

        jugadores = list(jugadores_activos_de(categoria))

        # La ultima novedad de cada uno: lo que el profe anoto la vez pasada.
        # Asi, al tomar lista, ya sabe con que viene cada chico.
        ultimas = {}
        for nota in Nota.objects.filter(jugador__in=jugadores).select_related('entrenador'):
            if nota.jugador_id not in ultimas:
                ultimas[nota.jugador_id] = nota

        filas = []
        for jugador in jugadores:
            filas.append({
                'jugador': jugador,
                'asistencia': marcas.get(jugador.id),
                'nota': ultimas.get(jugador.id),
            })
        data['filas'] = filas
        data['resumen'] = resumen_del_dia(categoria, fecha)
        data['entrena_hoy'] = categoria.entrena_hoy(fecha)

    return render(request, 'adm_asistencia/view.html', data)
