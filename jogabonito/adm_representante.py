# coding=utf-8
"""Modulo: representantes de los jugadores. Solo administradores."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.forms import RepresentanteForm
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import Representante

MODULO = 'adm_representante'


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

        if action == 'add':
            try:
                form = RepresentanteForm(request.POST)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                representante = form.save(commit=False)
                representante.save(request)
                return ok_json({'mensaje': 'Representante registrado.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'edit':
            try:
                representante = Representante.objects.get(pk=int(request.POST['id']))
                form = RepresentanteForm(request.POST, instance=representante)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                representante = form.save(commit=False)
                representante.save(request)
                return ok_json({'mensaje': 'Representante actualizado.'})
            except Representante.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                representante = Representante.objects.get(pk=int(request.POST['id']))
                if representante.jugadores.exists():
                    return bad_json(mensaje='No se puede eliminar: tiene jugadores asignados.')
                representante.delete()
                return ok_json({'mensaje': 'Representante eliminado.'})
            except Representante.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')

    if action == 'add':
        data['title'] = 'Nuevo representante'
        data['form'] = RepresentanteForm()
        return render(request, 'adm_representante/add.html', data)

    if action == 'edit':
        try:
            representante = Representante.objects.get(pk=int(request.GET['id']))
        except (Representante.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Editar representante'
        data['representante'] = representante
        data['form'] = RepresentanteForm(instance=representante)
        return render(request, 'adm_representante/edit.html', data)

    if action == 'delete':
        try:
            representante = Representante.objects.get(pk=int(request.GET['id']))
        except (Representante.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Eliminar representante'
        data['representante'] = representante
        return render(request, 'adm_representante/delete.html', data)

    if action == 'view':
        try:
            representante = Representante.objects.get(pk=int(request.GET['id']))
        except (Representante.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Ficha del representante'
        data['representante'] = representante
        data['jugadores'] = representante.jugadores.all().order_by('apellidos', 'nombres')
        return render(request, 'adm_representante/ficha.html', data)

    data['title'] = 'Representantes'
    buscar = (request.GET.get('s') or '').strip()
    representantes = Representante.objects.all()
    if buscar:
        representantes = representantes.filter(
            Q(nombres__icontains=buscar) | Q(apellidos__icontains=buscar) |
            Q(cedula__icontains=buscar) | Q(telefono__icontains=buscar) | Q(whatsapp__icontains=buscar)
        )
    data['search'] = buscar
    data['representantes'] = paginar(request, representantes, data, MODULO)
    data['total_representantes'] = Representante.objects.filter(activo=True).count()
    return render(request, 'adm_representante/view.html', data)
