# coding=utf-8
"""Modulo: administracion de entrenadores. Solo administradores."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render

from jogabonito.commonviews import adduserdata
from jogabonito.decorators import URL_LOGIN, last_access, secure_module, solo_administrador
from jogabonito.forms import EntrenadorForm, UsuarioEntrenadorForm
from jogabonito.funciones import bad_json, generar_nombre, ok_json, paginar, url_back
from jogabonito.models import ROL_ENTRENADOR, Entrenador, PerfilUsuario

MODULO = 'adm_entrenador'
URL_MODULO = '/sistema/%s' % MODULO


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
                form = EntrenadorForm(request.POST, request.FILES)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                entrenador = form.save(commit=False)
                if entrenador.fotografia:
                    entrenador.fotografia.name = generar_nombre('entrenador_', entrenador.fotografia.name)
                entrenador.save(request)
                return ok_json({'mensaje': 'Entrenador registrado.'})
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'edit':
            try:
                entrenador = Entrenador.objects.get(pk=int(request.POST['id']))
                form = EntrenadorForm(request.POST, request.FILES, instance=entrenador)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))
                entrenador = form.save(commit=False)
                if 'fotografia' in request.FILES:
                    entrenador.fotografia.name = generar_nombre('entrenador_', entrenador.fotografia.name)
                entrenador.save(request)
                return ok_json({'mensaje': 'Entrenador actualizado.'})
            except Entrenador.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        if action == 'delete':
            try:
                entrenador = Entrenador.objects.get(pk=int(request.POST['id']))
                if entrenador.categorias.exists():
                    return bad_json(mensaje='No se puede eliminar: el entrenador tiene categorias asignadas.')
                entrenador.delete()
                return ok_json({'mensaje': 'Entrenador eliminado.'})
            except Entrenador.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=9, ex=ex)

        if action == 'usuario':
            try:
                entrenador = Entrenador.objects.get(pk=int(request.POST['id']))
                form = UsuarioEntrenadorForm(request.POST, entrenador=entrenador)
                if not form.is_valid():
                    return bad_json(mensaje=primer_error(form))

                username = form.cleaned_data['username']
                clave = form.cleaned_data['password']
                usuario = entrenador.usuario

                if usuario is None:
                    usuario = User.objects.create_user(username=username, email=entrenador.email, password=clave)
                else:
                    usuario.username = username
                    usuario.email = entrenador.email
                    if clave:
                        usuario.set_password(clave)
                    usuario.save()

                usuario.first_name = entrenador.nombres[:150]
                usuario.last_name = entrenador.apellidos[:150]
                usuario.is_active = entrenador.activo
                usuario.save()

                grupo, _ = Group.objects.get_or_create(name='ENTRENADOR')
                usuario.groups.add(grupo)

                perfil = PerfilUsuario.objects.filter(usuario=usuario).first()
                if perfil is None:
                    perfil = PerfilUsuario(usuario=usuario, rol=ROL_ENTRENADOR)
                perfil.rol = ROL_ENTRENADOR
                perfil.telefono = entrenador.telefono
                perfil.activo = entrenador.activo
                perfil.save(request)

                entrenador.usuario = usuario
                entrenador.save(request)
                return ok_json({'mensaje': 'Acceso al sistema actualizado.'})
            except Entrenador.DoesNotExist:
                return bad_json(error=3)
            except Exception as ex:
                transaction.set_rollback(True)
                return bad_json(error=1, ex=ex)

        return bad_json(error=0)

    # ----------------------------- GET --------------------------------
    adduserdata(request, data)
    action = request.GET.get('action')

    if action == 'add':
        data['title'] = 'Nuevo entrenador'
        data['form'] = EntrenadorForm()
        return render(request, 'adm_entrenador/add.html', data)

    if action == 'edit':
        try:
            entrenador = Entrenador.objects.get(pk=int(request.GET['id']))
        except (Entrenador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Editar entrenador'
        data['entrenador'] = entrenador
        data['form'] = EntrenadorForm(instance=entrenador)
        return render(request, 'adm_entrenador/edit.html', data)

    if action == 'delete':
        try:
            entrenador = Entrenador.objects.get(pk=int(request.GET['id']))
        except (Entrenador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Eliminar entrenador'
        data['entrenador'] = entrenador
        return render(request, 'adm_entrenador/delete.html', data)

    if action == 'usuario':
        try:
            entrenador = Entrenador.objects.get(pk=int(request.GET['id']))
        except (Entrenador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Acceso al sistema'
        data['entrenador'] = entrenador
        data['form'] = UsuarioEntrenadorForm(entrenador=entrenador)
        return render(request, 'adm_entrenador/usuario.html', data)

    if action == 'view':
        try:
            entrenador = Entrenador.objects.get(pk=int(request.GET['id']))
        except (Entrenador.DoesNotExist, KeyError, ValueError):
            return url_back(request)
        data['title'] = 'Ficha del entrenador'
        data['entrenador'] = entrenador
        data['categorias'] = entrenador.categorias.all().order_by('hora_inicio')
        return render(request, 'adm_entrenador/ficha.html', data)

    data['title'] = 'Entrenadores'
    buscar = (request.GET.get('s') or '').strip()
    entrenadores = Entrenador.objects.all()
    if buscar:
        entrenadores = entrenadores.filter(
            Q(nombres__icontains=buscar) | Q(apellidos__icontains=buscar) |
            Q(cedula__icontains=buscar) | Q(telefono__icontains=buscar)
        )
    data['search'] = buscar
    data['entrenadores'] = paginar(request, entrenadores, data, MODULO)
    data['total_entrenadores'] = Entrenador.objects.filter(activo=True).count()
    return render(request, 'adm_entrenador/view.html', data)
