# coding=utf-8
"""Modulo: jugadores.

El administrador administra todo. El entrenador SOLO consulta los jugadores
de las categorias que tiene asignadas (el filtro se aplica en el queryset,
nunca se confia en el id que llega del navegador).
"""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import render

from jogabonito.acceso import categorias_permitidas, jugadores_permitidos
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.forms import JugadorForm, RepresentanteDelJugadorForm
from jogabonito.funciones import bad_json, generar_nombre, ok_json, paginar, url_back
from jogabonito.models import (
    ESTADOS_JUGADOR, JUGADOR_ACTIVO, MENSUALIDAD_PENDIENTE, Division, Jugador, Representante,
)

MODULO = 'adm_jugador'


def primer_error(form):
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
        action = request.POST.get('action')

        # Las notas las escribe quien esta en la cancha, asi que el entrenador
        # tambien puede (solo sobre los jugadores de sus grupos, como siempre).
        # Todo lo demas sigue siendo del administrador.
        # Todas las escrituras de este modulo son del administrador. Lo que
        # el entrenador anota de sus jugadores (notas y medidas) vive en
        # adm_evaluacion, que es el modulo que el si tiene.
        if not perfil.es_administrador():
            return bad_json(error=4)

        if action == 'add':
            try:
                form = JugadorForm(request.POST, request.FILES)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
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
                    return bad_json(mensaje=primer_error(form))
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

        # A un jugador NO se lo borra: con el se irian sus asistencias, sus
        # pagos y sus mediciones, que son el historial de la academia. El que
        # deja de venir se DESACTIVA: sale de las listas y no se le cobra mas,
        # pero todo lo suyo queda.
        if action == 'delete':
            return bad_json(mensaje='Los jugadores no se eliminan: se perderia todo su '
                                    'historial de asistencias, pagos y mediciones. '
                                    'Usa "Desactivar" y sale de las listas.')

        if action == 'representante':
            try:
                jugador = Jugador.objects.get(pk=int(request.POST['id']))
                form = RepresentanteDelJugadorForm(request.POST)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                representante = form.asignar(jugador, request)
                if representante is None:
                    return ok_json({'mensaje': 'El jugador quedo sin representante.'})
                return ok_json({'mensaje': 'Representante asignado: %s.' % representante.nombre_completo()})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

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

    if action in ('add', 'edit', 'delete', 'representante') and solo_lectura:
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
        # Ya no existe borrar: si alguien llega con el enlace viejo, se le
        # explica y se lo manda a desactivar.
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Los jugadores no se eliminan'
        data['jugador'] = jugador
        return render(request, 'adm_jugador/delete.html', data)

    if action == 'representante':
        if solo_lectura:
            return url_back(request)
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Representante de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['form'] = RepresentanteDelJugadorForm(jugador=jugador)
        return render(request, 'adm_jugador/representante.html', data)

    if action == 'view':
        try:
            jugador = permitidos.get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Ficha del jugador'
        data['jugador'] = jugador
        data['entrenadores'] = jugador.entrenadores()
        data['resumen'] = jugador.resumen_asistencia()
        # En la ficha van solo los ultimos: para ver todo estan las pantallas
        # de historial, que es donde un chico de anios se revisa de verdad.
        data['asistencias'] = jugador.ultimas_asistencias(3)
        data['mensualidades'] = jugador.mensualidades.order_by(
            F('periodo_inicio').desc(nulls_last=True), '-anio', '-mes')[:3]
        data['proximo_cobro'] = jugador.proximo_periodo()
        data['controles'] = list(jugador.controles_fisicos())[::-1][:6]
        data['ultimo_control'] = jugador.ultimo_control()
        data['crecimiento'] = jugador.crecimiento()
        data['notas'] = jugador.notas.select_related('entrenador')[:8]
        data['total_notas'] = jugador.notas.count()
        data['meses_que_debe'] = jugador.meses_que_debe()
        data['total_que_debe'] = jugador.total_que_debe()
        data['dias_de_atraso'] = jugador.dias_de_atraso()
        data['posicion_sugerida'] = jugador.posicion_sugerida()

        # La tela de arania y el detalle de donde destaca y donde le falta:
        # es lo primero que el usuario quiere ver del chico.
        data['radar'] = jugador.radar()
        comparativa = jugador.comparativa_categoria()
        data['fortalezas'] = [x for x in comparativa if x['posicion'] == 'fortaleza'][:3]
        data['a_mejorar'] = [x for x in comparativa if x['posicion'] == 'mejorar'][:3]
        data['resumen_base'] = jugador.resumen_desde_la_base()
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

    division_id = request.GET.get('division')
    if division_id:
        try:
            division = Division.objects.get(pk=int(division_id))
            desde, hasta = division.rango_de_nacimiento()
            jugadores = jugadores.filter(fecha_nacimiento__gte=desde, fecha_nacimiento__lte=hasta)
            data['division_id'] = division.id
        except (Division.DoesNotExist, TypeError, ValueError):
            pass

    # Cuanto debe cada uno, para verlo sin entrar a la ficha.
    pendientes = Q(mensualidades__estado=MENSUALIDAD_PENDIENTE)
    jugadores = jugadores.annotate(
        meses_pendientes=Count('mensualidades', filter=pendientes),
        deuda=Sum('mensualidades__valor', filter=pendientes),
    ).order_by('apellidos', 'nombres')

    cuenta = request.GET.get('cuenta')
    if cuenta == 'debe':
        jugadores = jugadores.filter(meses_pendientes__gt=0)
        data['cuenta_id'] = 'debe'
    elif cuenta == 'aldia':
        jugadores = jugadores.filter(meses_pendientes=0)
        data['cuenta_id'] = 'aldia'

    data['search'] = buscar
    data['categorias'] = categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio')
    data['estados'] = ESTADOS_JUGADOR
    data['divisiones'] = Division.objects.filter(activo=True)
    data['total_jugadores'] = permitidos.filter(estado=JUGADOR_ACTIVO).count()
    data['cuantos_deben'] = permitidos.filter(
        estado=JUGADOR_ACTIVO, mensualidades__estado=MENSUALIDAD_PENDIENTE).distinct().count()
    data['jugadores'] = paginar(request, jugadores, data, MODULO)
    return render(request, 'adm_jugador/view.html', data)
