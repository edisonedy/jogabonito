# Academia Joga Bonito — Sistema de gestion

Sistema Django para administrar UNA academia de futbol (jugadores, categorias,
entrenadores, representantes y, mas adelante, asistencia y mensualidades).

La estructura sigue el mismo patron de `C:\proyectos\jdsistemas`: el paquete del
proyecto es tambien la app principal, con un archivo por modulo (`adm_*.py`).

## Tecnologia

- Python 3.10, Django 5.2, PostgreSQL 17
- Django Templates + Bootstrap 5 (mobile first)
- JavaScript solo donde hace falta (modales via `data-modal-url`)

## Puesta en marcha

```bash
cd C:/proyectos/jogabonito
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py cargar_base --admin-clave "TuClaveSegura"
.venv/Scripts/python.exe manage.py runserver 8040
```

- Sistema: http://localhost:8040/sistema/
- Admin de Django: http://localhost:8040/admin/
- Usuario inicial: `admin` (la clave es la que pasaste en `--admin-clave`)

Agrega `--demo` a `cargar_base` para crear las categorias MANANA / TARDE / NOCHE.

Para probar con datos de ejemplo (entrenadores, jugadores y asistencia de las
ultimas semanas) y poder borrarlos despues sin tocar lo real:

```bash
.venv/Scripts/python.exe manage.py cargar_demo
.venv/Scripts/python.exe manage.py cargar_demo --borrar
```

La configuracion sensible vive en `.env` (ver `.env.example`).

## Estructura

```
jogabonito/
├── settings.py          configuracion (lee .env)
├── urls.py              /login, /admin, /sistema/
├── sistema_urls.py      una ruta por modulo
├── models.py            todos los modelos
├── forms.py             formularios y validaciones
├── funciones.py         ok_json / bad_json / MiPaginador / validar_cedula
├── decorators.py        secure_module, solo_administrador, last_access
├── commonviews.py       login, panel, mi cuenta, cambio de clave
├── adm_jugador.py       \
├── adm_categoria.py      |  un modulo = un archivo con una funcion view(request)
├── adm_entrenador.py     |
├── adm_representante.py /
└── management/commands/cargar_base.py
templates/
├── base_nueva.html      layout con sidebar + topbar + modal dinamico
├── panel.html           tarjetas de modulos
├── form_modal.html      formulario dentro del modal (POST por AJAX)
├── delete_modal.html    confirmacion de borrado
└── adm_*/               view.html, add.html, edit.html, delete.html, ficha.html
static/css/joga.css      marca Joga Bonito y tablas responsivas
```

### Como se agrega un modulo nuevo

1. Crear `jogabonito/adm_x.py` con una funcion `view(request)`.
2. Registrarla en `sistema_urls.py`.
3. Crear `templates/adm_x/view.html` (+ add/edit/delete si hace falta).
4. Agregar el `Modulo` en `cargar_base.py` y asignarlo a los grupos.

El decorador `@secure_module` compara el primer segmento de la URL
(`/sistema/adm_x` -> `adm_x`) contra los modulos de los grupos del usuario.

## Roles

| Rol | Puede |
|---|---|
| ADMINISTRADOR | todo: asistencia, jugadores, categorias, entrenadores, representantes |
| ENTRENADOR | registrar asistencia y consultar los jugadores de SUS categorias |

El filtro del entrenador se aplica en el queryset (`jugadores_permitidos`), no en
la plantilla: aunque mande un id a mano, no accede a fichas ajenas.

## Pruebas

```bash
.venv/Scripts/python.exe manage.py test jogabonito
```

## Fases

- [x] FASE 1: proyecto, usuarios/roles, entrenadores, categorias, jugadores, representantes
- [x] FASE 2: asistencia
- [ ] FASE 3: mensualidades
- [ ] FASE 4: dashboard, reportes, observaciones
- [x] FASE 5: landing publica y solicitudes de inscripcion

## Asistencia (FASE 2)

Pantalla `/sistema/adm_asistencia`: se elige grupo y fecha, y cada jugador tiene
cuatro botones grandes (Presente / Falta / Atraso / Justificado). Cada toque es
un POST pequeno que responde JSON y actualiza los contadores sin recargar.

Reglas que aplica el servidor (no el navegador):

- un solo registro por jugador + categoria + fecha (restriccion en la base);
  volver a marcar ACTUALIZA el registro, no lo duplica
- no se acepta una fecha futura
- el jugador debe pertenecer a esa categoria y estar ACTIVO
- el entrenador solo puede tocar sus categorias
- "Marcar presentes a los que faltan" nunca pisa lo que ya se marco a mano

El porcentaje de asistencia cuenta PRESENTE y ATRASO sobre el total de
registros; se muestra en la ficha del jugador y en su historial
(`/sistema/adm_asistencia?action=historial&id=<jugador>`).

## Pagina publica (FASE 5)

La raiz `/` es la landing de la academia. Todo su contenido sale de dos lugares:

- **`.env`**: nombre, lema, descripcion, direccion, telefono, WhatsApp, correo,
  redes, y los datos del director (`ACADEMIA_DIRECTOR*`). Si cambias el `.env`
  hay que reiniciar el servidor para que se vea.
- **La base de datos**: los grupos, dias, horarios y valores que se muestran en
  "Elige el horario que te sirve" son las categorias activas del sistema.

Las fortalezas y las credenciales del director se editan en `jogabonito/landing.py`
(listas `FORTALEZAS` y `CREDENCIALES_DIRECTOR`).

Para poner el logo: deja el archivo en `static/images/logo.png` (o .jpg/.webp) y
la pagina lo usa sola, en el navbar, el hero, el footer y al compartir el enlace.

El boton "Quiero inscribirme" guarda una `SolicitudInscripcion` que el
administrador revisa en `/sistema/adm_solicitud` (estados NUEVA → CONTACTADO →
INSCRITO / DESCARTADO, con nota interna y enlace directo a WhatsApp).

Defensas del formulario publico: CSRF, validacion en el servidor, campo trampa
para robots y un tope de `SOLICITUDES_MAXIMAS_POR_HORA` por IP.

**Antes de publicarla**, borra los datos de ejemplo con
`manage.py cargar_demo --borrar`: los contadores del hero (jugadores,
entrenadores, grupos) salen de la base real.
