# coding=utf-8
"""Modulo: jornadas de prueba y progreso de cada jugador.

Flujo:
  1. Se crea la evaluacion: fecha, grupo, titulo y QUE indicadores se van a medir.
  2. Se abre la planilla y se va anotando el valor de cada jugador (guarda al vuelo).
  3. Cada jugador tiene su ficha de progreso: primera marca, ultima, mejor marca,
     si mejoro o empeoro, y como esta frente al promedio de su grupo.

El entrenador trabaja solo con sus categorias; el administrador con todas.
"""
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render

from jogabonito.acceso import categoria_permitida, categorias_permitidas, jugadores_permitidos
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.forms import EvaluacionForm
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import AREAS_INDICADOR, Evaluacion, Indicador, Jugador, Medicion

MODULO = 'adm_evaluacion'


def _primer_error(form):
    return next(iter(form.errors.values()))[0]


def evaluaciones_permitidas(perfil):
    base = Evaluacion.objects.select_related('categoria')
    if perfil.es_administrador():
        return base
    return base.filter(categoria__in=categorias_permitidas(perfil))


def _evaluacion_de(perfil, valor):
    try:
        return evaluaciones_permitidas(perfil).get(pk=int(valor))
    except (Evaluacion.DoesNotExist, TypeError, ValueError):
        return None


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

        # ---- crear / editar la jornada de pruebas --------------------
        if action in ('add', 'edit'):
            try:
                evaluacion = None
                if action == 'edit':
                    evaluacion = _evaluacion_de(perfil, request.POST.get('id'))
                    if evaluacion is None:
                        return bad_json(error=4)
                    if evaluacion.cerrada:
                        return bad_json(mensaje='La evaluacion esta cerrada.')

                form = EvaluacionForm(request.POST, instance=evaluacion,
                                      categorias=categorias_permitidas(perfil).filter(activo=True))
                if not form.is_valid():
                    return bad_json(mensaje=_primer_error(form))

                evaluacion = form.save(commit=False)
                evaluacion.save(request)
                form.save_m2m()
                return ok_json({'mensaje': 'Evaluacion guardada.',
                                'redirect_url': '/sistema/adm_evaluacion?action=planilla&id=%s' % evaluacion.id})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- anotar el valor de un jugador ---------------------------
        if action == 'medir':
            try:
                evaluacion = _evaluacion_de(perfil, request.POST.get('evaluacion'))
                if evaluacion is None:
                    return bad_json(error=4)
                if evaluacion.cerrada:
                    return bad_json(mensaje='La evaluacion esta cerrada.')

                jugador = evaluacion.jugadores().filter(pk=int(request.POST['jugador'])).first()
                if jugador is None:
                    return bad_json(error=4)

                indicador = evaluacion.indicadores.filter(pk=int(request.POST['indicador'])).first()
                if indicador is None:
                    return bad_json(error=4)

                crudo = (request.POST.get('valor') or '').strip().replace(',', '.')

                # Vacio significa borrar la marca.
                if crudo == '':
                    Medicion.objects.filter(evaluacion=evaluacion, jugador=jugador,
                                            indicador=indicador).delete()
                    return ok_json({'borrado': True, 'avance': evaluacion.avance()})

                try:
                    valor = Decimal(crudo)
                except InvalidOperation:
                    return bad_json(mensaje='Escribe un numero valido.')

                if not indicador.rango_valido(valor):
                    return bad_json(mensaje='El valor debe estar entre %s y %s.' % (
                        indicador.valor_minimo, indicador.valor_maximo))

                medicion = Medicion.objects.filter(
                    evaluacion=evaluacion, jugador=jugador, indicador=indicador
                ).first()
                if medicion is None:
                    medicion = Medicion(evaluacion=evaluacion, jugador=jugador, indicador=indicador)
                medicion.valor = valor
                medicion.save(request)

                mejoro = medicion.mejoro()
                return ok_json({
                    'texto': medicion.texto(),
                    'mejoro': mejoro,
                    'avance': evaluacion.avance(),
                })
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- cerrar o reabrir ----------------------------------------
        if action == 'cerrar':
            try:
                evaluacion = _evaluacion_de(perfil, request.POST.get('id'))
                if evaluacion is None:
                    return bad_json(error=4)
                evaluacion.cerrada = not evaluacion.cerrada
                evaluacion.save(request)
                return ok_json({'mensaje': 'Evaluacion cerrada.' if evaluacion.cerrada
                                else 'Evaluacion reabierta.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- eliminar (solo el administrador) ------------------------
        if action == 'delete':
            try:
                if not perfil.es_administrador():
                    return bad_json(error=4)
                evaluacion = _evaluacion_de(perfil, request.POST.get('id'))
                if evaluacion is None:
                    return bad_json(error=4)
                evaluacion.indicadores.clear()
                evaluacion.delete()
                return ok_json({'mensaje': 'Evaluacion eliminada.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')
    data['es_administrador'] = perfil.es_administrador()

    if action == 'add':
        data['title'] = 'Nueva evaluacion'
        data['form'] = EvaluacionForm(categorias=categorias_permitidas(perfil).filter(activo=True))
        if not Indicador.objects.filter(activo=True).exists():
            data['sin_indicadores'] = True
        return render(request, 'adm_evaluacion/add.html', data)

    if action in ('edit', 'delete', 'planilla'):
        evaluacion = _evaluacion_de(perfil, request.GET.get('id'))
        if evaluacion is None:
            return url_back(request)
        data['evaluacion'] = evaluacion

        if action == 'delete':
            data['title'] = 'Eliminar evaluacion'
            return render(request, 'adm_evaluacion/delete.html', data)

        if action == 'edit':
            data['title'] = 'Editar evaluacion'
            data['form'] = EvaluacionForm(instance=evaluacion,
                                          categorias=categorias_permitidas(perfil).filter(activo=True))
            return render(request, 'adm_evaluacion/edit.html', data)

        # Planilla de captura: filas = jugadores, columnas = indicadores.
        indicadores = list(evaluacion.indicadores_ordenados())
        marcas = {
            (m.jugador_id, m.indicador_id): m
            for m in evaluacion.mediciones.select_related('indicador')
        }
        filas = []
        for jugador in evaluacion.jugadores():
            celdas = []
            for indicador in indicadores:
                medicion = marcas.get((jugador.id, indicador.id))
                celdas.append({
                    'indicador': indicador,
                    'medicion': medicion,
                    'valor': medicion.valor if medicion else '',
                    'mejoro': medicion.mejoro() if medicion else None,
                })
            filas.append({'jugador': jugador, 'celdas': celdas})

        data['title'] = evaluacion.titulo
        data['indicadores'] = indicadores
        data['filas'] = filas
        data['avance'] = evaluacion.avance()
        return render(request, 'adm_evaluacion/planilla.html', data)

    if action == 'progreso':
        try:
            jugador = jugadores_permitidos(perfil).get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        data['title'] = 'Progreso de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['progreso'] = jugador.progreso()
        data['comparativa'] = jugador.comparativa_categoria()
        data['fortalezas'] = [x for x in data['comparativa'] if x['posicion'] == 'fortaleza']
        data['a_mejorar'] = [x for x in data['comparativa'] if x['posicion'] == 'mejorar']
        data['resumen_asistencia'] = jugador.resumen_asistencia()
        return render(request, 'adm_evaluacion/progreso.html', data)

    data['title'] = 'Evaluaciones'
    evaluaciones = evaluaciones_permitidas(perfil).prefetch_related('indicadores')

    categoria_id = request.GET.get('categoria')
    if categoria_id:
        categoria = categoria_permitida(perfil, categoria_id)
        if categoria is None:
            return url_back(request)
        evaluaciones = evaluaciones.filter(categoria=categoria)
        data['categoria_id'] = categoria.id

    data['categorias'] = categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio')
    data['areas'] = AREAS_INDICADOR
    data['evaluaciones'] = paginar(request, evaluaciones, data, MODULO)
    return render(request, 'adm_evaluacion/view.html', data)
