# coding=utf-8
"""Utilidades compartidas por los modulos del sistema."""
import json
import os
from datetime import date, datetime

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse

MENSAJES_ERROR = {
    0: 'Solicitud incorrecta.',
    1: 'Error al guardar los datos. Verifique la informacion ingresada.',
    2: 'Error al eliminar el registro.',
    3: 'Error al obtener los datos.',
    4: 'No tiene permisos para realizar esta accion.',
    5: 'Error al generar la informacion.',
    6: 'Los datos no son validos, revise el formulario.',
    7: 'El registro ya existe.',
    9: 'No se puede eliminar porque tiene registros relacionados.',
}


def ok_json(data=None, **kwargs):
    """Respuesta JSON de exito para los formularios modales."""
    contenido = {'result': 'ok'}
    if isinstance(data, dict):
        contenido.update(data)
    if kwargs:
        contenido.update(kwargs)
    return HttpResponse(json.dumps(contenido, default=str), content_type='application/json')


def bad_json(mensaje=None, error=None, ex=None, extradata=None):
    """Respuesta JSON de error. Nunca expone el traceback en produccion."""
    contenido = {'result': 'bad', 'icono': 'warning', 'titulo': 'Advertencia'}
    if mensaje:
        contenido['mensaje'] = mensaje
    elif error is not None:
        contenido['mensaje'] = MENSAJES_ERROR.get(error, MENSAJES_ERROR[0])
    else:
        contenido['mensaje'] = 'Error en el sistema.'

    if ex is not None and settings.DEBUG:
        contenido['detalle'] = str(ex)

    if extradata:
        contenido.update(extradata)
    return HttpResponse(json.dumps(contenido, default=str), content_type='application/json')


def url_back(request, ex=None):
    """Devuelve al mismo modulo cuando una accion GET no es valida."""
    return HttpResponse(request.path)


def convertir_fecha(cadena):
    """Convierte 'dd-mm-aaaa' o 'aaaa-mm-dd' a date."""
    cadena = (cadena or '').strip()
    if not cadena:
        return None
    separador = '-' if '-' in cadena else '/'
    partes = cadena.split(separador)
    if len(partes) != 3:
        return None
    if len(partes[0]) == 4:
        return date(int(partes[0]), int(partes[1]), int(partes[2]))
    return date(int(partes[2]), int(partes[1]), int(partes[0]))


def generar_nombre(prefijo, original):
    """Nombre unico y seguro para un archivo subido."""
    extension = ''
    if original and original.rfind('.') > 0:
        extension = original[original.rfind('.'):].lower()
    ahora = datetime.now()
    return '%s%s%s' % (prefijo, ahora.strftime('%Y%m%d%H%M%S%f'), extension)


def validar_imagen(archivo):
    """Valida extension y tamano de una imagen subida. Devuelve (ok, mensaje)."""
    if not archivo:
        return True, ''
    extension = os.path.splitext(archivo.name)[1].lower().replace('.', '')
    if extension not in settings.IMAGEN_EXTENSIONES_PERMITIDAS:
        return False, 'Formato no permitido. Use: %s.' % ', '.join(settings.IMAGEN_EXTENSIONES_PERMITIDAS)
    if archivo.size > settings.IMAGEN_TAMANO_MAXIMO:
        return False, 'La imagen supera el tamano maximo de %s MB.' % (settings.IMAGEN_TAMANO_MAXIMO // (1024 * 1024))
    return True, ''


def validar_cedula(numero):
    """Valida una cedula ecuatoriana. Devuelve True/False."""
    numero = (numero or '').strip()
    if len(numero) != 10 or not numero.isdigit():
        return False
    provincia = int(numero[0:2])
    if provincia < 1 or provincia > 24:
        return False
    if int(numero[2]) > 5:
        return False
    suma = 0
    for indice in range(9):
        digito = int(numero[indice])
        if indice % 2 == 0:
            digito *= 2
            if digito > 9:
                digito -= 9
        suma += digito
    verificador = (10 - (suma % 10)) % 10
    return verificador == int(numero[9])


class MiPaginador(Paginator):
    """Paginador con rangos, igual al que usa jdsistemas en las tablas."""

    def __init__(self, object_list, per_page, orphans=0, allow_empty_first_page=True, rango=5):
        super().__init__(object_list, per_page, orphans=orphans, allow_empty_first_page=allow_empty_first_page)
        self.rango = rango
        self.paginas = []
        self.primera_pagina = False
        self.ultima_pagina = False
        self.ellipsis_izquierda = 0
        self.ellipsis_derecha = 0

    def rangos_paginado(self, pagina):
        izquierda = max(pagina - self.rango, 1)
        derecha = min(pagina + self.rango, self.num_pages)
        self.paginas = range(izquierda, derecha + 1)
        self.primera_pagina = izquierda > 1
        self.ultima_pagina = derecha < self.num_pages
        self.ellipsis_izquierda = izquierda - 1
        self.ellipsis_derecha = derecha + 1
        return self.paginas


def paginar(request, queryset, data, modulo, por_pagina=25):
    """Pagina un queryset y deja en `data` lo que esperan las plantillas."""
    paginador = MiPaginador(queryset, por_pagina)
    pagina_actual = 1
    if 'page' in request.GET:
        try:
            pagina_actual = int(request.GET['page'])
        except (TypeError, ValueError):
            pagina_actual = 1
    if pagina_actual < 1:
        pagina_actual = 1
    if pagina_actual > paginador.num_pages:
        pagina_actual = paginador.num_pages

    pagina = paginador.page(pagina_actual)
    request.session['paginador'] = pagina_actual
    request.session['paginador_url'] = modulo

    data['paging'] = paginador
    data['rangospaging'] = paginador.rangos_paginado(pagina_actual)
    data['page'] = pagina
    return pagina.object_list
