# coding=utf-8
"""Modulo: categorias / grupos de entrenamiento. Solo administradores."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.forms import CategoriaForm
from jogabonito.funciones import bad_json, ok_json, paginar, url_back
from jogabonito.models import Categoria

MODULO = 'adm_categoria'


def _primer_error(form):
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
                form = CategoriaForm(request.POST)
                if not form.is_valid():
                    return bad_json(mensaje=_primer_error(form))
                categoria = form.save(commit=False)
                categoria.save(request)
                form.save_m2m()
                return ok_json({'mensaje': 'Categoria registrada.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'edit':
            try:
                categoria = Categoria.objects.get(pk=int(request.POST['id']))
                form = CategoriaForm(request.POST, instance=categoria)
                if not form.is_valid():
                    return bad_json(mensaje=_primer_error(form))
                categoria = form.save(commit=False)
                categoria.save(request)
                form.save_m2m()
                return ok_json({'mensaje': 'Categoria actualizada.'})
            except Categoria.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                categoria = Categoria.objects.get(pk=int(request.POST['id']))
                if categoria.jugadores.exists():
                    return bad_json(mensaje='No se puede eliminar: la categoria tiene jugadores registrados.')
                categoria.entrenadores.clear()
                categoria.delete()
                return ok_json({'mensaje': 'Categoria eliminada.'})
            except Categoria.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')

    if action == 'add':
        data['title'] = 'Nueva categoria'
        data['form'] = CategoriaForm()
        return render(request, 'adm_categoria/add.html', data)

    if action == 'edit':
        try:
            categoria = Categoria.objects.get(pk=int(request.GET['id']))
        except (Categoria.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Editar categoria'
        data['categoria'] = categoria
        data['form'] = CategoriaForm(instance=categoria)
        return render(request, 'adm_categoria/edit.html', data)

    if action == 'delete':
        try:
            categoria = Categoria.objects.get(pk=int(request.GET['id']))
        except (Categoria.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Eliminar categoria'
        data['categoria'] = categoria
        return render(request, 'adm_categoria/delete.html', data)

    if action == 'view':
        try:
            categoria = Categoria.objects.get(pk=int(request.GET['id']))
        except (Categoria.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Ficha de la categoria'
        data['categoria'] = categoria
        data['jugadores'] = categoria.jugadores_activos()
        return render(request, 'adm_categoria/ficha.html', data)

    data['title'] = 'Categorias'
    buscar = (request.GET.get('s') or '').strip()
    categorias = Categoria.objects.all().prefetch_related('entrenadores')
    if buscar:
        categorias = categorias.filter(Q(nombre__icontains=buscar) | Q(descripcion__icontains=buscar))
    data['search'] = buscar
    data['categorias'] = paginar(request, categorias, data, MODULO)
    data['total_categorias'] = Categoria.objects.filter(activo=True).count()
    return render(request, 'adm_categoria/view.html', data)
