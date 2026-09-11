# coding=utf-8
from django.contrib import admin

from jogabonito.models import (
    Asistencia, Categoria, Entrenador, GruposModulos, Jugador, Modulo, PerfilUsuario,
    Representante, SolicitudInscripcion,
)


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'url', 'orden', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'url')


@admin.register(GruposModulos)
class GruposModulosAdmin(admin.ModelAdmin):
    list_display = ('grupo',)
    filter_horizontal = ('modulos',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'activo')
    list_filter = ('rol', 'activo')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')


@admin.register(Entrenador)
class EntrenadorAdmin(admin.ModelAdmin):
    list_display = ('apellidos', 'nombres', 'telefono', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombres', 'apellidos', 'cedula')


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'horario_texto', 'dias_texto', 'valor_mensual', 'activo')
    list_filter = ('activo',)
    filter_horizontal = ('entrenadores',)


@admin.register(Representante)
class RepresentanteAdmin(admin.ModelAdmin):
    list_display = ('apellidos', 'nombres', 'telefono', 'parentesco', 'activo')
    list_filter = ('activo', 'parentesco')
    search_fields = ('nombres', 'apellidos', 'cedula')


@admin.register(Jugador)
class JugadorAdmin(admin.ModelAdmin):
    list_display = ('apellidos', 'nombres', 'categoria', 'estado')
    list_filter = ('estado', 'categoria')
    search_fields = ('nombres', 'apellidos', 'cedula')


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'jugador', 'categoria', 'estado')
    list_filter = ('estado', 'categoria', 'fecha')
    search_fields = ('jugador__nombres', 'jugador__apellidos')
    date_hierarchy = 'fecha'


@admin.register(SolicitudInscripcion)
class SolicitudInscripcionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'edad', 'categoria', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'categoria')
    search_fields = ('nombre', 'telefono')
    readonly_fields = ('origen_ip',)
