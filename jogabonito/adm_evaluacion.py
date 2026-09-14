# coding=utf-8
"""Modulo: jornadas de prueba y progreso de cada jugador.

Flujo:
  1. Se crea la evaluacion: fecha, grupo, titulo y QUE indicadores se van a medir.
  2. Se abre la planilla y se va anotando el valor de cada jugador (guarda al vuelo).
  3. Cada jugador tiene su ficha de progreso: primera marca, ultima, mejor marca,
     si mejoro o empeoro, y como esta frente al promedio de su grupo.

El entrenador trabaja solo con sus categorias; el administrador con todas.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render

from jogabonito.acceso import categoria_permitida, categorias_permitidas, jugadores_permitidos
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.forms import ControlFisicoForm, EvaluacionForm, NotaForm
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import (
    AREAS_INDICADOR, COLORES_AREA, JUGADOR_ACTIVO, ControlFisico, Evaluacion, Indicador,
    Jugador, Medicion, Nota, TipoEvaluacion,
)

MODULO = 'adm_evaluacion'


def primer_error(form):
    return next(iter(form.errors.values()))[0]


def evaluaciones_permitidas(perfil):
    base = Evaluacion.objects.select_related('categoria')
    if perfil.es_administrador():
        return base
    return base.filter(categoria__in=categorias_permitidas(perfil))


def evaluacion_permitida(perfil, valor):
    try:
        return evaluaciones_permitidas(perfil).get(pk=int(valor))
    except (Evaluacion.DoesNotExist, TypeError, ValueError):
        return None


def indicadores_por_area():
    """Los indicadores agrupados por area, para el selector de la evaluacion.

    Con 100 indicadores una lista plana de casillas es inmanejable: asi se
    puede buscar, abrir un area a la vez y marcarla completa.
    """
    nombres = dict(AREAS_INDICADOR)
    grupos = {}

    for indicador in Indicador.objects.filter(activo=True).order_by('area', 'orden', 'nombre'):
        grupos.setdefault(indicador.area, []).append(indicador)

    return [
        {
            'area': area,
            'nombre': nombres.get(area, ''),
            'color': COLORES_AREA.get(area, 'secondary'),
            'indicadores': lista,
        }
        for area, lista in sorted(grupos.items())
    ]


def fecha_pedida(request, clave, origen=None):
    """Lee una fecha de la pantalla; si viene mal escrita, se ignora."""
    datos = origen if origen is not None else request.GET
    valor = (datos.get(clave) or '').strip()
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
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
                    evaluacion = evaluacion_permitida(perfil, request.POST.get('id'))
                    if evaluacion is None:
                        return bad_json(error=4)
                    if evaluacion.cerrada:
                        return bad_json(mensaje='La evaluacion esta cerrada.')

                form = EvaluacionForm(request.POST, instance=evaluacion,
                                      categorias=categorias_permitidas(perfil).filter(activo=True))
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                evaluacion = form.save(commit=False)
                evaluacion.save(request)
                form.save_m2m()
                destino = 'planilla' if evaluacion.indicadores.exists() else 'elegir'
                return ok_json({
                    'mensaje': 'Evaluacion guardada.',
                    'redirect_url': '/sistema/adm_evaluacion?action=%s&id=%s' % (
                        destino, evaluacion.id),
                })
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- notas del profe sobre el ninio --------------------------
        # Aqui SI escribe el entrenador: es el que esta en la cancha.
        if action == 'nota':
            try:
                jugador = jugadores_permitidos(perfil).get(pk=int(request.POST['jugador']))
                form = NotaForm(request.POST)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                nota = form.save(commit=False)
                nota.jugador = jugador
                nota.entrenador = perfil.entrenador()
                nota.save(request)
                return ok_json({'mensaje': 'Nota guardada.'})
            except Jugador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- peso y estatura -----------------------------------------
        if action in ('control', 'editcontrol'):
            try:
                jugador = jugadores_permitidos(perfil).get(pk=int(request.POST['jugador']))

                control = None
                if action == 'editcontrol':
                    control = ControlFisico.objects.get(pk=int(request.POST['id']), jugador=jugador)

                form = ControlFisicoForm(request.POST, instance=control, jugador=jugador)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                control = form.save(commit=False)
                control.jugador = jugador
                control.save(request)
                return ok_json({'mensaje': 'Control guardado.'})
            except (Jugador.DoesNotExist, ControlFisico.DoesNotExist):
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'borrarcontrol':
            try:
                control = ControlFisico.objects.select_related('jugador').get(pk=int(request.POST['id']))
                if not jugadores_permitidos(perfil).filter(pk=control.jugador_id).exists():
                    return bad_json(error=4)
                control.delete()
                return ok_json({'mensaje': 'Control eliminado.'})
            except ControlFisico.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        if action == 'borrarnota':
            try:
                nota = Nota.objects.select_related('jugador').get(pk=int(request.POST['id']))
                if not jugadores_permitidos(perfil).filter(pk=nota.jugador_id).exists():
                    return bad_json(error=4)
                nota.delete()
                return ok_json({'mensaje': 'Nota eliminada.'})
            except Nota.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        # ---- que se va a medir en esta prueba ------------------------
        if action == 'elegir':
            try:
                evaluacion = evaluacion_permitida(perfil, request.POST.get('id'))
                if evaluacion is None:
                    return bad_json(error=4)
                if evaluacion.cerrada:
                    return bad_json(mensaje='La evaluacion esta cerrada.')

                pedidos = request.POST.getlist('indicadores')
                indicadores = list(Indicador.objects.filter(id__in=pedidos, activo=True))
                if not indicadores:
                    return bad_json(mensaje='Marca al menos una cosa para medir.')

                # Lo que se saca y ya tenia valores se avisa, no se borra a escondidas.
                quitados = evaluacion.indicadores.exclude(
                    id__in=[i.id for i in indicadores]).values_list('id', flat=True)
                con_datos = evaluacion.mediciones.filter(indicador_id__in=list(quitados)).count()

                evaluacion.indicadores.set(indicadores)

                mensaje = 'Se van a medir %s cosas.' % len(indicadores)
                if con_datos:
                    mensaje += (' Ojo: %s marca%s de lo que quitaste dejan de verse en la '
                                'planilla.' % (con_datos, '' if con_datos == 1 else 's'))

                return ok_json({
                    'mensaje': mensaje,
                    'redirect_url': '/sistema/adm_evaluacion?action=planilla&id=%s' % evaluacion.id,
                })
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- la prueba de ingreso de UN jugador ----------------------
        # El chico llega, el profe lo coge aparte y lo mide. No es una jornada
        # del grupo y casi nunca cae el mismo dia que la de los demas.
        if action == 'ingreso':
            try:
                jugador = jugadores_permitidos(perfil).select_related('categoria').get(
                    pk=int(request.POST['jugador']))

                dia = fecha_pedida(request, 'fecha', request.POST) or date.today()
                if dia > date.today():
                    return bad_json(mensaje='No se puede tomar una prueba de un dia que no llega.')

                tipo = TipoEvaluacion.objects.filter(es_inicial=True, activo=True).first()
                indicadores = list(Indicador.objects.filter(activo=True).order_by(
                    'area', 'orden', 'nombre'))
                if not indicadores:
                    return bad_json(mensaje='Todavia no hay indicadores. Crealos en Que medimos.')

                evaluacion = Evaluacion(
                    categoria=jugador.categoria,
                    jugador=jugador,
                    tipo=tipo,
                    fecha=dia,
                    titulo='PRUEBA DE INGRESO DE %s' % jugador.nombre_completo(),
                    observacion='Con esto llego a la academia. Es su punto de partida.',
                )
                evaluacion.save(request)
                evaluacion.indicadores.set(indicadores)

                return ok_json({
                    'mensaje': 'Prueba de ingreso creada. Ahora anota sus marcas.',
                    'redirect_url': '/sistema/adm_evaluacion?action=planilla&id=%s' % evaluacion.id,
                })
            except Jugador.DoesNotExist:
                return bad_json(error=4)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        # ---- anotar el valor de un jugador ---------------------------
        if action == 'medir':
            try:
                evaluacion = evaluacion_permitida(perfil, request.POST.get('evaluacion'))
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

                # El dia real en que se le tomo ESA marca. Viene de la planilla
                # (cada jugador puede haber dado la prueba otro dia); si no,
                # queda el dia en que se esta anotando.
                pedida = fecha_pedida(request, 'fecha', request.POST)
                if pedida and evaluacion.abarca(pedida):
                    medicion.fecha = pedida
                elif medicion.fecha is None:
                    medicion.fecha = evaluacion.dia_para_medir()

                medicion.save(request)

                mejoro = medicion.mejoro()
                return ok_json({
                    'texto': medicion.texto(),
                    'mejoro': mejoro,
                    'dia': medicion.dia().strftime('%d/%m/%Y'),
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
                evaluacion = evaluacion_permitida(perfil, request.POST.get('id'))
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
                evaluacion = evaluacion_permitida(perfil, request.POST.get('id'))
                if evaluacion is None:
                    return bad_json(error=4)

                # Si ya se le tomo a alguien, eso es historial del chico: se
                # cierra la prueba, no se la borra.
                cuantas = evaluacion.mediciones.count()
                if cuantas:
                    return bad_json(
                        mensaje='No se puede eliminar: ya tiene %s medicion%s tomada%s. '
                                'Si ya no se usa, cierrala.'
                                % (cuantas, '' if cuantas == 1 else 'es',
                                   '' if cuantas == 1 else 's'))

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
        data['areas_indicadores'] = indicadores_por_area()
        data['indicadores_marcados'] = []
        data['form'] = EvaluacionForm(categorias=categorias_permitidas(perfil).filter(activo=True))
        if not Indicador.objects.filter(activo=True).exists():
            data['sin_indicadores'] = True
        return render(request, 'adm_evaluacion/add.html', data)

    if action in ('edit', 'delete', 'planilla'):
        evaluacion = evaluacion_permitida(perfil, request.GET.get('id'))
        if evaluacion is None:
            return url_back(request)
        data['evaluacion'] = evaluacion

        if action == 'delete':
            data['title'] = 'Eliminar evaluacion'
            return render(request, 'adm_evaluacion/delete.html', data)

        if action == 'edit':
            data['title'] = 'Editar evaluacion'
            data['areas_indicadores'] = indicadores_por_area()
            data['indicadores_marcados'] = list(
                evaluacion.indicadores.values_list('id', flat=True))
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
                    'dia': medicion.dia() if medicion else None,
                    'mejoro': medicion.mejoro() if medicion else None,
                })

            # El dia con el que se van a guardar las marcas de ESTE jugador:
            # el que ya tenga alguna anotada, o el dia en que se esta midiendo.
            dias = [c['dia'] for c in celdas if c['dia']]
            filas.append({
                'jugador': jugador,
                'celdas': celdas,
                'dia': max(dias) if dias else evaluacion.dia_para_medir(),
            })

        data['title'] = evaluacion.titulo
        data['indicadores'] = indicadores
        data['filas'] = filas
        data['dia_sugerido'] = evaluacion.dia_para_medir()
        data['avance'] = evaluacion.avance()
        return render(request, 'adm_evaluacion/planilla.html', data)

    if action == 'nota':
        try:
            jugador = jugadores_permitidos(perfil).get(pk=int(request.GET['jugador']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Nota sobre %s' % jugador.como_le_dicen()
        data['jugador'] = jugador

        # Si viene desde la asistencia, la nota queda con la fecha de ESA clase.
        dia = fecha_pedida(request, 'fecha')
        inicial = {'fecha': dia} if dia and dia <= date.today() else {}
        data['form'] = NotaForm(initial=inicial)
        return render(request, 'adm_evaluacion/nota.html', data)

    if action in ('control', 'editcontrol'):
        try:
            jugador = jugadores_permitidos(perfil).get(pk=int(request.GET['jugador']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        control = None
        if action == 'editcontrol':
            try:
                control = ControlFisico.objects.get(pk=int(request.GET['id']), jugador=jugador)
            except (ControlFisico.DoesNotExist, KeyError, ValueError):
                return url_back(request)

        data['title'] = 'Peso y estatura de %s' % jugador.como_le_dicen()
        data['jugador'] = jugador
        data['control'] = control
        data['form'] = ControlFisicoForm(instance=control, jugador=jugador)
        return render(request, 'adm_evaluacion/control.html', data)

    if action == 'borrarcontrol':
        try:
            control = ControlFisico.objects.select_related('jugador').get(pk=int(request.GET['id']))
        except (ControlFisico.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        if not jugadores_permitidos(perfil).filter(pk=control.jugador_id).exists():
            return url_back(request)
        data['title'] = 'Eliminar control'
        data['control'] = control
        return render(request, 'adm_evaluacion/borrarcontrol.html', data)

    if action == 'borrarnota':
        try:
            nota = Nota.objects.select_related('jugador').get(pk=int(request.GET['id']))
        except (Nota.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        if not jugadores_permitidos(perfil).filter(pk=nota.jugador_id).exists():
            return url_back(request)
        data['title'] = 'Eliminar nota'
        data['nota'] = nota
        return render(request, 'adm_evaluacion/borrarnota.html', data)

    if action == 'elegir':
        evaluacion = evaluacion_permitida(perfil, request.GET.get('id'))
        if evaluacion is None:
            return url_back(request)

        data['title'] = 'Que se va a medir'
        data['evaluacion'] = evaluacion
        data['areas_indicadores'] = indicadores_por_area()
        data['indicadores_marcados'] = list(evaluacion.indicadores.values_list('id', flat=True))
        return render(request, 'adm_evaluacion/elegir.html', data)

    if action == 'ingreso':
        try:
            jugador = jugadores_permitidos(perfil).select_related('categoria').get(
                pk=int(request.GET['jugador']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        data['title'] = 'Prueba de ingreso'
        data['jugador'] = jugador
        data['tipo'] = TipoEvaluacion.objects.filter(es_inicial=True, activo=True).first()
        data['cuantos'] = Indicador.objects.filter(activo=True).count()
        data['ya_tiene'] = jugador.linea_base() != {}
        data['hoy'] = date.today()
        return render(request, 'adm_evaluacion/ingreso.html', data)

    if action == 'bajando':
        data['title'] = 'Quien viene bajando'
        jugadores = jugadores_permitidos(perfil).filter(
            estado=JUGADOR_ACTIVO).select_related('categoria')

        categoria_id = request.GET.get('categoria')
        if categoria_id:
            categoria = categoria_permitida(perfil, categoria_id)
            if categoria is None:
                return url_back(request)
            jugadores = jugadores.filter(categoria=categoria)
            data['categoria_id'] = categoria.id

        filas = []
        subiendo = 0
        for jugador in jugadores:
            bajas = jugador.retrocesos()
            if bajas:
                filas.append({'jugador': jugador, 'bajas': bajas, 'cuantos': len(bajas)})
            else:
                subiendo += 1

        filas.sort(key=lambda x: -x['cuantos'])
        data['filas'] = filas
        data['bien'] = subiendo
        data['categorias'] = categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio')
        return render(request, 'adm_evaluacion/bajando.html', data)

    if action == 'progreso':
        try:
            jugador = jugadores_permitidos(perfil).get(pk=int(request.GET['id']))
        except (Jugador.DoesNotExist, KeyError, ValueError):
            return url_back(request)

        desde = fecha_pedida(request, 'desde')
        hasta = fecha_pedida(request, 'hasta')

        data['title'] = 'Progreso de %s' % jugador.nombre_completo()
        data['jugador'] = jugador
        data['progreso'] = jugador.progreso(desde, hasta)
        data['desde'] = desde
        data['hasta'] = hasta
        data['hay_filtro'] = bool(desde or hasta)
        data['total_mediciones'] = jugador.cuantas_mediciones()
        data['desde_la_base'] = jugador.como_llego_y_como_va()
        data['resumen_base'] = jugador.resumen_desde_la_base()
        data['primera_medicion'] = jugador.primera_medicion()
        data['ultima_medicion'] = jugador.ultima_medicion()
        data['radar'] = jugador.radar()
        data['afinidades'] = jugador.afinidad_posiciones()
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

    tipo_id = request.GET.get('tipo')
    if tipo_id:
        try:
            evaluaciones = evaluaciones.filter(tipo_id=int(tipo_id))
            data['tipo_id'] = int(tipo_id)
        except (TypeError, ValueError):
            pass

    data['categorias'] = categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio')
    data['tipos'] = TipoEvaluacion.objects.filter(activo=True)
    data['areas'] = AREAS_INDICADOR
    data['evaluaciones'] = paginar(request, evaluaciones, data, MODULO)
    return render(request, 'adm_evaluacion/view.html', data)
