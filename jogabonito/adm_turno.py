# coding=utf-8
"""Modulo: quien esta a cargo de cada grupo.

Lo mas simple que se puede: un grupo, un profe encargado. Se elige de una
lista y se guarda solo. Cuando haga falta se cambia.

Si un dia lo cubre otro porque el de siempre se enfermo, eso se conversa: el
sistema no se mete y cualquiera del cuerpo tecnico puede tomar lista.
"""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render

from jogabonito.acceso import categorias_permitidas
from jogabonito.commonviews import adduserdata, perfil_de
from jogabonito.decorators import URL_LOGIN, last_access, secure_module
from jogabonito.funciones import bad_json, ok_json, url_back
from jogabonito.models import Categoria, Entrenador

MODULO = 'adm_turno'


def grupos_con_encargado(categorias):
    """Una fila por grupo con su encargado y los profes que se le pueden poner.

    Solo salen los entrenadores que ya estan asignados a ese grupo: quien da
    clases ahi se define en la ficha del grupo (Categorias), y aqui solo se
    elige a cual de ellos le toca estar a cargo.
    """
    return [
        {
            'categoria': categoria,
            'encargado': categoria.encargado,
            'candidatos': list(categoria.entrenadores.filter(activo=True)),
        }
        for categoria in categorias
    ]


def grupos_de_hoy(categorias, dia=None):
    """Los grupos que entrenan hoy y quien esta a cargo. Lo usa el tablero."""
    return [
        {'categoria': categoria, 'encargado': categoria.encargado}
        for categoria in categorias
        if categoria.entrena_hoy(dia)
    ]


def grupos_a_cargo_de(entrenador, categorias):
    """Los grupos de los que ese profe es el encargado."""
    if entrenador is None:
        return []
    return [c for c in categorias if c.encargado_id == entrenador.id]


@login_required(login_url=URL_LOGIN)
@secure_module
@last_access
@transaction.atomic()
def view(request):
    data = {}
    perfil = perfil_de(request.user)
    if perfil is None or not perfil.activo:
        return url_back(request)

    solo_lectura = not perfil.es_administrador()

    if request.method == 'POST':
        if solo_lectura:
            return bad_json(error=4)

        if request.POST.get('action') == 'asignar':
            try:
                categoria = Categoria.objects.get(pk=int(request.POST['categoria']))

                entrenador = None
                valor = (request.POST.get('entrenador') or '').strip()

                if valor:
                    entrenador = Entrenador.objects.get(pk=int(valor))
                    if not entrenador.activo:
                        return bad_json(mensaje='%s no esta activo.' % entrenador.nombre_completo())

                    if not categoria.entrenadores.filter(pk=entrenador.id).exists():
                        return bad_json(
                            mensaje='%s no da clases en %s. Agregalo al grupo desde Categorias '
                                    '(boton editar) y vuelve aqui.'
                                    % (entrenador.nombre_completo(), categoria.nombre))

                categoria.encargado = entrenador
                categoria.save(request)

                if entrenador:
                    mensaje = '%s queda a cargo de %s.' % (
                        entrenador.nombre_completo(), categoria.nombre)
                else:
                    mensaje = '%s quedo sin encargado.' % categoria.nombre
                return ok_json({'mensaje': mensaje})
            except (Categoria.DoesNotExist, Entrenador.DoesNotExist):
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        return bad_json(error=0)

    # ------------------------------ GET -------------------------------
    adduserdata(request, data)
    categorias = list(categorias_permitidas(perfil).filter(activo=True).order_by('hora_inicio'))

    data['title'] = 'Quien esta a cargo'
    data['solo_lectura'] = solo_lectura
    data['grupos'] = grupos_con_encargado(categorias)
    data['sin_encargado'] = len([g for g in data['grupos'] if not g['encargado']])
    data['mis_grupos'] = grupos_a_cargo_de(perfil.entrenador(), categorias)
    return render(request, 'adm_turno/view.html', data)
