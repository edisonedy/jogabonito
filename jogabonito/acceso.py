# coding=utf-8
"""Alcance de datos por rol.

El administrador ve toda la academia; el entrenador solo las categorias que
tiene asignadas. Estas funciones devuelven QUERYSETS ya filtrados: las vistas
consultan sobre ellos en vez de confiar en los ids que llegan del navegador.
"""
from jogabonito.models import JUGADOR_ACTIVO, Categoria, Jugador


def categorias_permitidas(perfil):
    if perfil is None:
        return Categoria.objects.none()
    if perfil.es_administrador():
        return Categoria.objects.all()
    entrenador = perfil.entrenador()
    if not entrenador:
        return Categoria.objects.none()
    return entrenador.categorias.all()


def jugadores_permitidos(perfil):
    base = Jugador.objects.select_related('categoria', 'representante')
    if perfil is None:
        return base.none()
    if perfil.es_administrador():
        return base
    entrenador = perfil.entrenador()
    if not entrenador:
        return base.none()
    return base.filter(categoria__entrenadores=entrenador).distinct()


def categoria_permitida(perfil, categoria_id):
    """Devuelve la categoria si el usuario puede trabajar con ella, o None."""
    try:
        return categorias_permitidas(perfil).get(pk=int(categoria_id))
    except (Categoria.DoesNotExist, TypeError, ValueError):
        return None


def jugadores_activos_de(categoria):
    return Jugador.objects.filter(categoria=categoria, estado=JUGADOR_ACTIVO).order_by('apellidos', 'nombres')
