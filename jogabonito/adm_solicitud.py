# coding=utf-8
"""Modulo: solicitudes de inscripcion que llegan desde la pagina publica."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import (
    ESTADOS_SOLICITUD, SOLICITUD_INSCRITO, SOLICITUD_NUEVA, Categoria, SolicitudInscripcion,
)

MODULO = 'adm_solicitud'
ESTADOS_VALIDOS = dict(ESTADOS_SOLICITUD)


@login_required(login_url=URL_LOGIN)
@secure_module
@solo_administrador
@last_access
@transaction.atomic()
def view(request):
    data = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'estado':
            try:
                solicitud = SolicitudInscripcion.objects.get(pk=int(request.POST['id']))
                estado = int(request.POST.get('estado', 0))
                if estado not in ESTADOS_VALIDOS:
                    return bad_json(error=6)
                solicitud.estado = estado
                solicitud.nota_interna = (request.POST.get('nota_interna') or '').strip()[:2000]
                solicitud.save(request)
                return ok_json({'mensaje': 'Solicitud actualizada.'})
            except SolicitudInscripcion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                solicitud = SolicitudInscripcion.objects.get(pk=int(request.POST['id']))
                # La que ya entro a la academia queda como constancia de como
                # llego ese alumno.
                if solicitud.estado == SOLICITUD_INSCRITO:
                    return bad_json(mensaje='No se puede eliminar: esa solicitud ya se '
                                            'convirtio en alumno. Es la constancia de como '
                                            'llego.')
                solicitud.delete()
                return ok_json({'mensaje': 'Solicitud eliminada.'})
            except SolicitudInscripcion.DoesNotExist:
                return bad_json(error=3)
            except (KeyError, TypeError, ValueError):
                return bad_json(error=6)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=2, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')

    if action in ('gestionar', 'delete'):
        try:
            solicitud = SolicitudInscripcion.objects.get(pk=int(request.GET['id']))
        except (SolicitudInscripcion.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['solicitud'] = solicitud
        data['estados'] = ESTADOS_SOLICITUD
        if action == 'delete':
            data['title'] = 'Eliminar solicitud'
            return render(request, 'adm_solicitud/delete.html', data)
        data['title'] = 'Gestionar solicitud'
        return render(request, 'adm_solicitud/gestionar.html', data)

    data['title'] = 'Solicitudes de inscripcion'
    buscar = (request.GET.get('s') or '').strip()
    solicitudes = SolicitudInscripcion.objects.select_related('categoria')

    if buscar:
        solicitudes = solicitudes.filter(Q(nombre__icontains=buscar) | Q(telefono__icontains=buscar))

    estado = request.GET.get('estado')
    if estado:
        try:
            solicitudes = solicitudes.filter(estado=int(estado))
            data['estado_id'] = int(estado)
        except (TypeError, ValueError):
            pass

    data['search'] = buscar
    data['estados'] = ESTADOS_SOLICITUD
    data['categorias'] = Categoria.objects.filter(activo=True)
    data['total_nuevas'] = SolicitudInscripcion.objects.filter(estado=SOLICITUD_NUEVA).count()
    data['solicitudes'] = paginar(request, solicitudes, data, MODULO)
    return render(request, 'adm_solicitud/view.html', data)
