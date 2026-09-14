# coding=utf-8
"""Modulo: catalogo de lo que se le mide al jugador (y las posiciones).

Aqui el administrador arma su propia lista de pruebas: el nombre, en que area
entra, si se califica del 1 al 10, con un numero o con un tiempo, y si mejorar
significa subir o bajar ese numero.
"""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.forms import IndicadorForm, PosicionForm, TipoEvaluacionForm
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import AREAS_INDICADOR, Indicador, Posicion, TipoEvaluacion

MODULO = 'adm_indicador'


def primer_error(form):
    return next(iter(form.errors.values()))[0]


@login_required(login_url=URL_LOGIN)
@secure_module
@solo_administrador
@last_access
@transaction.atomic()
def view(request):
    data = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        # ------------------------- indicadores -------------------------
        if action in ('add', 'edit'):
            try:
                indicador = None
                if action == 'edit':
                    indicador = Indicador.objects.get(pk=int(request.POST['id']))
                form = IndicadorForm(request.POST, instance=indicador)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                indicador = form.save(commit=False)
                indicador.save(request)
                return ok_json({'mensaje': 'Indicador guardado.'})
            except Indicador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                indicador = Indicador.objects.get(pk=int(request.POST['id']))
                if indicador.mediciones.exists():
                    return bad_json(mensaje='No se puede eliminar: ya tiene mediciones registradas. '
                                            'Desactivalo para dejar de usarlo.')
                if indicador.evaluaciones.exists():
                    return bad_json(mensaje='No se puede eliminar: esta dentro de una evaluacion.')
                indicador.delete()
                return ok_json({'mensaje': 'Indicador eliminado.'})
            except Indicador.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        # -------------------------- posiciones -------------------------
        if action in ('addposicion', 'editposicion'):
            try:
                posicion = None
                if action == 'editposicion':
                    posicion = Posicion.objects.get(pk=int(request.POST['id']))
                form = PosicionForm(request.POST, instance=posicion)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                posicion = form.save(commit=False)
                posicion.save(request)
                return ok_json({'mensaje': 'Posicion guardada.'})
            except Posicion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delposicion':
            try:
                posicion = Posicion.objects.get(pk=int(request.POST['id']))
                if posicion.jugadores.exists():
                    return bad_json(mensaje='No se puede eliminar: hay jugadores en esa posicion.')
                posicion.delete()
                return ok_json({'mensaje': 'Posicion eliminada.'})
            except Posicion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        if action in ('addtipo', 'edittipo'):
            try:
                tipo = None
                if action == 'edittipo':
                    tipo = TipoEvaluacion.objects.get(pk=int(request.POST['id']))
                form = TipoEvaluacionForm(request.POST, instance=tipo)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                tipo = form.save(commit=False)
                tipo.save(request)
                # Solo un tipo puede ser la prueba inicial.
                if tipo.es_inicial:
                    TipoEvaluacion.objects.exclude(pk=tipo.pk).update(es_inicial=False)
                return ok_json({'mensaje': 'Tipo de evaluacion guardado.'})
            except TipoEvaluacion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'deltipo':
            try:
                tipo = TipoEvaluacion.objects.get(pk=int(request.POST['id']))
                if tipo.evaluaciones.exists():
                    return bad_json(mensaje='No se puede eliminar: hay evaluaciones de ese tipo. '
                                            'Desactivalo para dejar de usarlo.')
                tipo.delete()
                return ok_json({'mensaje': 'Tipo de evaluacion eliminado.'})
            except TipoEvaluacion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')

    if action == 'add':
        data['title'] = 'Nuevo indicador'
        data['form'] = IndicadorForm()
        return render(request, 'adm_indicador/add.html', data)

    if action in ('edit', 'delete'):
        try:
            indicador = Indicador.objects.get(pk=int(request.GET['id']))
        except (Indicador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['indicador'] = indicador
        if action == 'delete':
            data['title'] = 'Eliminar indicador'
            return render(request, 'adm_indicador/delete.html', data)
        data['title'] = 'Editar indicador'
        data['form'] = IndicadorForm(instance=indicador)
        return render(request, 'adm_indicador/edit.html', data)

    if action == 'addposicion':
        data['title'] = 'Nueva posicion'
        data['form'] = PosicionForm()
        return render(request, 'adm_indicador/addposicion.html', data)

    if action in ('editposicion', 'delposicion'):
        try:
            posicion = Posicion.objects.get(pk=int(request.GET['id']))
        except (Posicion.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['posicion'] = posicion
        if action == 'delposicion':
            data['title'] = 'Eliminar posicion'
            return render(request, 'adm_indicador/delposicion.html', data)
        data['title'] = 'Editar posicion'
        data['form'] = PosicionForm(instance=posicion)
        return render(request, 'adm_indicador/editposicion.html', data)

    if action == 'addtipo':
        data['title'] = 'Nuevo tipo de evaluacion'
        data['form'] = TipoEvaluacionForm()
        return render(request, 'adm_indicador/addtipo.html', data)

    if action in ('edittipo', 'deltipo'):
        try:
            tipo = TipoEvaluacion.objects.get(pk=int(request.GET['id']))
        except (TipoEvaluacion.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['tipo'] = tipo
        if action == 'deltipo':
            data['title'] = 'Eliminar tipo de evaluacion'
            return render(request, 'adm_indicador/deltipo.html', data)
        data['title'] = 'Editar tipo de evaluacion'
        data['form'] = TipoEvaluacionForm(instance=tipo)
        return render(request, 'adm_indicador/edittipo.html', data)

    data['title'] = 'Que medimos'
    buscar = (request.GET.get('s') or '').strip()
    indicadores = Indicador.objects.all()
    if buscar:
        indicadores = indicadores.filter(Q(nombre__icontains=buscar) | Q(descripcion__icontains=buscar))

    area = request.GET.get('area')
    if area:
        try:
            indicadores = indicadores.filter(area=int(area))
            data['area_id'] = int(area)
        except (TypeError, ValueError):
            pass

    data['search'] = buscar
    data['areas'] = AREAS_INDICADOR
    data['total_activos'] = Indicador.objects.filter(activo=True).count()
    data['posiciones'] = Posicion.objects.all()
    data['tipos'] = TipoEvaluacion.objects.all()
    data['indicadores'] = paginar(request, indicadores, data, MODULO, por_pagina=30)
    return render(request, 'adm_indicador/view.html', data)
