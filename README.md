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
| ADMINISTRADOR | todo: asistencia, evaluaciones, jugadores, categorias, entrenadores, representantes, solicitudes y el catalogo de indicadores |
| ENTRENADOR | registrar asistencia, tomar evaluaciones y consultar los jugadores de SUS categorias |

El filtro del entrenador se aplica en el queryset (`jugadores_permitidos`), no en
la plantilla: aunque mande un id a mano, no accede a fichas ajenas.

## Pruebas

```bash
.venv/Scripts/python.exe manage.py test jogabonito
```

## Fases

- [x] FASE 1: proyecto, usuarios/roles, entrenadores, categorias, jugadores, representantes
- [x] FASE 2: asistencia
- [x] FASE 3: mensualidades
- [x] FASE 4: tablero (reportes en pantalla y observaciones quedan pendientes)
- [x] FASE 5: landing publica y solicitudes de inscripcion
- [x] EXTRA: evaluaciones medibles por jugador (indicadores, planilla y progreso)
- [ ] SIGUIENTE: informe del jugador redactado con IA sobre estas mediciones

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

**La foto del director** se busca sola: basta con dejar `director.jpg` (o .png,
.jpeg, .webp) en `static/images/`. Si se prefiere otra ruta o una URL, se pone
en `ACADEMIA_DIRECTOR_FOTO` del `.env`. En el bloque de cuerpo tecnico el
director va arriba, a lo ancho, y los profes de cada grupo van debajo.

### Identidad visual

La landing usa los colores del escudo: **verde** (#17a44b / #0f8a3d), **azul
marino** (#2b2a6e) y **dorado** (#ffd200), con Anton para los titulares y
Kaushan Script para la palabra "Bonito". El credito de HORUS va discreto en el
pie: la pagina es de la academia.

- **Logo**: deja el archivo en `static/images/logo.png` (o .jpg/.webp) y la
  pagina lo usa sola en el navbar, el hero, el pie y al compartir el enlace.
  Mientras no este, se dibuja un escudo de respaldo con los mismos colores
  (`templates/landing/_emblema.html`).
- **Galeria**: las fotos que dejes en `static/images/galeria/` aparecen en la
  seccion "Asi entrenamos" (las 8 primeras, en orden alfabetico). Carpeta
  vacia = seccion oculta.
- **Valores** (Disciplina, Respeto, Trabajo en equipo, Pasion): franja azul
  debajo del hero, igual que en su arte oficial. Se editan en `landing.py`.
- **Cuerpo tecnico**: el director sale del `.env` y los profesores salen de la
  base (entrenadores activos, solo nombre y foto: ningun telefono se publica).
- **Anios de trayectoria**: `ACADEMIA_ANIOS` en el `.env`. Es solo el numero,
  sin fechas ni aniversarios. Vacio = no se muestra.

El boton "Quiero inscribirme" guarda una `SolicitudInscripcion` que el
administrador revisa en `/sistema/adm_solicitud` (estados NUEVA → CONTACTADO →
INSCRITO / DESCARTADO, con nota interna y enlace directo a WhatsApp).

Defensas del formulario publico: CSRF, validacion en el servidor, campo trampa
para robots y un tope de `SOLICITUDES_MAXIMAS_POR_HORA` por IP.

**Antes de publicarla**, borra los datos de ejemplo con
`manage.py cargar_demo --borrar`: los contadores del hero (jugadores,
entrenadores, grupos) salen de la base real.

## Medir a cada jugador (evaluaciones)

La idea: **cada jugador tiene su plan y se mide**. El sistema no trae metricas
fijas: el administrador arma su propia lista.

**1. Que medimos** (`/sistema/adm_indicador`, solo administrador)
Catalogo de indicadores. Cada uno tiene:

- **area**: tecnica, fisica, tactica o actitud
- **tipo de medida**: escala 1 a 10, numero con unidad (reps, m, cm, goles) o
  tiempo en segundos
- **sentido de la mejora**: en la escala y en los numeros mejorar es subir; en
  el tiempo mejorar es bajar (el sistema lo calcula solo)
- **rango valido**, para que nadie anote un 15 sobre 10

En la misma pantalla, la pestana **Posiciones** define los puestos que luego se
eligen en la ficha del jugador ("la posicion que le gusta"), junto con el pie
habil y el dorsal.

`cargar_base` deja 13 indicadores y 10 posiciones como punto de partida.

**2. La jornada de pruebas** (`/sistema/adm_evaluacion`)
Se crea con fecha, grupo, titulo y **que indicadores se van a tomar ese dia**.
Eso abre la planilla: una tarjeta por jugador con un campo por indicador, que
guarda al momento de escribir y va mostrando el porcentaje completado y una
flecha verde o roja comparando con la toma anterior. Al terminar se puede
**cerrar** la evaluacion para que nadie la cambie.

**3. El progreso** (`?action=progreso&id=<jugador>`, tambien desde la ficha)
Por cada indicador: cuantas tomas, primera marca, ultima, mejor marca y si
mejoro o bajo. Arriba, dos bloques calculados contra el promedio del grupo:

- **Donde destaca** (esta por encima del promedio de sus companieros)
- **Lo que hay que trabajar** (esta por debajo)

Todo queda guardado con fecha y con quien lo anoto, que es justamente lo que
mas adelante va a leer el asistente de IA para redactar el informe del jugador.
En codigo esos datos salen de `Jugador.progreso()`, `Jugador.fortalezas()` y
`Jugador.aspectos_a_mejorar()`.

Reglas que aplica el servidor: no se puede medir a un jugador de otro grupo ni
a uno retirado, ni un indicador que no entra en esa prueba; el valor respeta el
rango del indicador; una evaluacion cerrada no admite cambios; y el entrenador
solo trabaja con sus categorias.

## Credito del desarrollador

El sistema muestra quien lo desarrolla en tres lugares: el pie de la pagina
publica, la pantalla de ingreso y el sidebar del sistema. Sale del `.env`:

```
DESARROLLADOR_NOMBRE=HORUS
DESARROLLADOR_LEMA=Soluciones Tecnologicas
DESARROLLADOR_URL=          # si la pones, el credito enlaza ahi
DESARROLLADOR_WHATSAPP=0999955936   # si no hay URL, enlaza al WhatsApp
DESARROLLADOR_COLOR=#009FE3
```

Si `DESARROLLADOR_NOMBRE` queda vacio, el credito no se dibuja en ningun lado.

Para que aparezca el logo real de HORUS en vez del rombo azul, deja el archivo
en `static/images/horus.svg` (o .png / .jpg / .webp) y el sistema lo toma solo.

## Tablero

`/sistema/dashboard` es la primera tarjeta del panel. Muestra, siempre dentro
del alcance del usuario (el entrenador solo ve sus grupos):

- jugadores activos, grupos, asistencia de hoy y solicitudes nuevas
- **Hoy en la cancha**: que grupos entrenan hoy segun sus dias y cuantos faltan
  por marcar
- **A quien hay que llamar**: jugadores por debajo del 70% de asistencia en los
  ultimos 30 dias (con al menos 3 registros, para no alarmar por una falta)
- como va cada grupo, con su rango de edad y cuantos jugadores se le pasaron
- ultimas pruebas con su tipo, y cuantos jugadores siguen sin ninguna medicion
- proximos cumpleanios de los siguientes 30 dias

## Grupos por edad

Cada categoria puede tener `edad_minima` y `edad_maxima` ademas de su horario,
asi que un grupo puede ser "Manana, 6 a 9 anios". Dejar las edades vacias
significa "todas las edades". El sistema **avisa** cuando un jugador se paso del
rango (en el tablero), pero no lo mueve solo: esa decision es del entrenador.

## Tipos de evaluacion y prueba inicial

En **Que medimos** hay una pestana de tipos de evaluacion: diagnostica inicial,
seguimiento semanal, evaluacion mensual, prueba final... y los que quieras
agregar. El tipo marcado como **inicial** es la linea base del jugador: con que
llego a la academia. Solo uno puede estar marcado asi a la vez.

## Tela de arania

En la pantalla de progreso, el radar resume al jugador en cuatro ejes: tecnica,
fisica, tactica y actitud. Como los indicadores no se miden igual, cada uno se
lleva a una escala 0-100:

- las notas del 1 al 10 se comparan contra su propio maximo (medida absoluta)
- los tiempos y las cantidades se comparan contra el mejor y el peor **de su
  grupo**, invirtiendo el sentido cuando mejorar significa bajar el numero

Por eso un eje puede decir "sin medir": o no se ha tomado ese indicador, o hace
falta medir a por lo menos dos jugadores del grupo para poder comparar.

Ojo con el idioma: con `LANGUAGE_CODE='es-ec'` Django escribe los decimales con
coma, y un SVG (o un `input type=number`) descarta `x="150,0"`. Por eso las
coordenadas del radar se arman como texto en `templatetags/joga_extras.py` y las
planillas usan `|unlocalize`.

## Mensualidades

El precio vive en el **grupo**, no en el jugador: todos los de MANANA pagan lo
que cueste MANANA (25 dolares por defecto). Sobre eso:

1. si el jugador tiene **descuento** (beca, hermano, convenio), se le resta ese
   porcentaje,
2. si aviso que no viene unos **dias**, se le cobran solo los dias que si
   entrena de ese periodo.

`Jugador.explicacion_precio()` arma el texto que se ve en pantalla
("valor de MANANA, 20% de descuento (hermano en la academia)").

Subir el precio de un grupo le sube a todos sus jugadores **desde la proxima
generacion**: lo ya generado no cambia, porque el valor se copia a la
mensualidad cuando se crea.

### El mes se abre solo

No hay que acordarse de generar nada. Cuando se termina el periodo de un
jugador, el sistema le abre el siguiente **al dia siguiente** (`cobros.py`).
Corre en dos momentos:

- cada vez que se entra al modulo de Mensualidades (y avisa cuantas abrio),
- con `python manage.py poner_al_dia`, por si se quiere dejar programado en el
  servidor.

Reglas:

- no importa si pago o no el mes anterior: si sigue viniendo, se le sigue
  cobrando,
- deja de abrirse si el jugador ya no esta activo o si le apagan el
  interruptor **"cobrarle cada mes"** (`Jugador.cobro_activo`, en el modal de
  cobro de su ficha),
- al volver a prenderlo, se pone al dia desde donde quedo,
- nunca se adelanta: solo abre periodos que ya arrancaron.

El boton **Cobro automatico** de la lista no es obligatorio: muestra a quien le
toca su proximo mes y en cuantos dias, y permite revisar en el momento.

**Agregar a uno** crea la mensualidad de un solo jugador, eligiendo las fechas
del periodo y el valor. Es para el que entra suelto o para un cobro aparte. Si
no se tocan las fechas, se usan las que le corresponden por su ingreso.

**Generar el mes** (dentro del modal de cobro automatico) sigue existiendo para
el caso raro de generarle el mes de golpe a un grupo entero.

**Cada jugador vence el dia en que ingreso**: si entro un 22, se le cobra el 22
de cada mes (si el mes es mas corto, el ultimo dia). Y no se le generan meses
anteriores a su fecha de ingreso, asi que el que entra en junio no aparece
debiendo enero.

**El cobro no es por mes calendario, es por dias**: cada mensualidad guarda su
`periodo_inicio` y `periodo_fin`. El periodo del jugador va del dia en que
ingreso al dia anterior del mes siguiente, asi que no siempre son 30 dias:
puede ser 28, 29, 30 o 31. El que entro un 13 tiene periodos 13/09 al 12/10,
13/10 al 12/11, y asi.

### A que mes pertenece un periodo

Al mes en que **arranca**, no al que termina. Si el jugador entro un 23, su
periodo del 23/09 al 22/10 es la mensualidad de **septiembre**. Es la misma
regla de cualquier suscripcion: se cobra por adelantado el dia aniversario y el
recibo lleva la fecha en que empieza el servicio.

Por eso `Mensualidad.save()` deriva `mes` y `anio` de `periodo_inicio`: el mes
es una etiqueta para agrupar y buscar, la verdad son las fechas.

### Continuidad de la deuda

El mes nuevo se abre aunque el anterior no este pagado, asi que la deuda se
acumula en vez de perderse. Para leerla de un vistazo:

- `Jugador.cubierto_hasta()`: hasta que dia esta pagado **sin huecos** (se
  corta en el primer mes pendiente, aunque haya pagado uno posterior),
- `Jugador.debe_desde()`: el dia en que arranca la deuda mas vieja,
- `Jugador.estado_de_cuenta()`: la frase que sale en la ficha
  ("Debe 3 meses, desde el 28/07/2026" o "Al dia, cubierto hasta el 22/10/2026").

**Cuando avisan que no viene**: en el cobro se pone cuantos DIAS falta y el
motivo. Se prorratea sobre los dias reales de ese periodo, no sobre un mes
teorico: 7 dias de un periodo de 31 no pesan lo mismo que 7 de uno de 28.
La pantalla muestra cuanto vale el dia. Si es el periodo entero, tambien esta
el estado EXONERADO.

Una mensualidad pendiente pasada de la fecha se muestra como **ATRASADA** (en
rojo, con los dias de atraso). La pantalla **Quien debe** lista a los deudores
ordenados por antiguedad del atraso, con cuantos meses debe, cuanto suma y el
boton de WhatsApp al representante.

Al abrir el cobro, la **fecha de pago viene puesta en hoy**, que es lo que pasa
casi siempre; si se cobro otro dia se cambia.

Las fechas se pueden corregir al cobrar: el modal de cobro trae
`periodo_inicio`, `periodo_fin` y el vencimiento. Si se dejan vacias, se
conservan las que tenia. El valor por dia se recalcula con el periodo nuevo, y
la cadena del cobro automatico sigue desde la fecha fin corregida.

Una mensualidad pagada no se puede borrar: primero hay que devolverla a
pendiente.

**Lo unico que la base no deja repetir es el periodo** (`jugador` +
`periodo_inicio`), no el mes del calendario: un jugador puede tener dos
periodos que empiecen en el mismo mes si le corrigieron las fechas. El mes y el
anio son solo la etiqueta y se derivan del dia en que arranca el periodo.

## En que posicion rinde mejor

Cada posicion define **cuanto pesa cada area** (tecnica, fisica, tactica,
actitud) de 0 a 3; eso se edita en **Que medimos > Posiciones**. Por ejemplo, el
arquero pide fisico 3 y actitud 3; el volante ofensivo, tecnica 3 y tactica 3.

`Jugador.afinidad_posiciones()` cruza esos pesos con los puntajes de su tela de
arania y devuelve los puestos ordenados por afinidad (0 a 100), marcando ademas
**la posicion que al jugador le gusta**. Asi se ve si lo que quiere jugar
coincide con lo que hoy hace mejor, sin obligar a nadie: la idea es que todos
jueguen de todo y con el tiempo se especialicen.

Como el catalogo de indicadores incluye **estatura, peso corporal y fuerza**, el
historial tambien sirve para ver como va creciendo y como cambia su perfil
fisico con el tiempo.

## Convenciones de codigo

- Nombres de funciones en espaniol y **sin guion bajo al inicio**: `primer_error`,
  `resumen_del_dia`, `cumpleanios_proximos`. Nada de `_helper` ni `__cosas`.
- Cada modulo es un archivo `adm_x.py` con una sola funcion `view(request)`.
- Los helpers de plantilla viven en `templatetags/joga_extras.py`.
- Nada de `height:100%` en bloques que se apilan en la misma columna: se
  desbordan sobre el pie. Para eso esta `.columna-bloques` + `.bloque-crece`.

## Ficha del jugador

Se reorganizo en bloques en vez de una lista larga: cabecera verde con el nombre
y sus datos rapidos (grupo, edad, posicion, estado y si debe), cuatro cifras
(asistencia, cuanto paga, cuanto debe y afinidad de posicion) y tres columnas:
datos personales, representante + grupo, y cuentas con los ultimos meses.

Desde ahi tambien se **asigna o se crea el representante** sin salir de la ficha:
el boton del bloque Representante abre un modal donde se elige uno ya registrado
o se llenan los datos del nuevo y queda asignado de una vez.

## Ver todas las mediciones (y por rango de fechas)

La pantalla de progreso de un jugador (`adm_evaluacion?action=progreso&id=N`)
tiene un filtro **desde / hasta**. Sin filtro sale toda su historia; con filtro,
solo ese tramo — y lo que cambia no es solo la lista: la primera marca, la
ultima y la evolucion se recalculan **dentro del rango**, asi se puede mirar
"como estuvo en vacaciones" o "desde que empezo el campeonato".

En la columna **Tomas** cada indicador se despliega con un clic y muestra
TODAS sus mediciones con su fecha y la prueba en que se tomo. Arriba a la
derecha sale cuantas mediciones tiene en total y entre que fechas.

En el codigo es `Jugador.progreso(desde, hasta)`; cada fila trae su
`historial` completo.

## Quien debe, desde la lista de jugadores

La lista de jugadores (solo para administradores) muestra en la columna
Mensualidad cuanto debe cada uno y cuantos meses, o "al dia" en verde, y avisa
si tiene el cobro pausado. Arriba hay un filtro **deban o no / solo los que
deben / solo los que estan al dia** y un chip rojo con cuantos deben, que
filtra al hacerle clic.

La deuda se calcula en el mismo queryset (`annotate` con Count y Sum de las
mensualidades pendientes), no consultando jugador por jugador.

Cada fila tiene ademas el boton de **cobrarle un mes** a ese estudiante, que
abre el mismo modal de "Agregar a uno" con el jugador ya elegido.

## Como le dicen (apodo)

`Jugador.apodo` guarda el nombre con el que le gusta que le llamen. Sale en la
cabecera de su ficha, en la lista de jugadores y en la pantalla de asistencia,
que es donde el profe lo busca a la carrera. `como_le_dicen()` devuelve el
apodo o, si no tiene, su primer nombre.

## Notas del profe sobre cada ninio

El modelo `Nota` (jugador, fecha, tipo, texto, entrenador) es la memoria de la
academia: dentro de un anio nadie se acuerda de por que un chico dejo de venir
dos semanas, pero la nota si. Hay cuatro tipos: **como va**, **para
felicitarlo**, **hay que estar pendiente** y **salud o lesion**, cada uno con
su color.

Se escriben desde la ficha del jugador (bloque "Notas del profe") y desde la
pantalla de quien viene bajando. Cada nota queda firmada: el nombre del
entrenador que la escribio, o ADMINISTRACION.

**Aqui el entrenador SI escribe**, aunque el resto del modulo de jugadores sea
solo del administrador: es el que esta en la cancha. Solo puede anotar a los
jugadores de sus grupos (`jugadores_permitidos`).

## Quien viene bajando

`Jugador.retrocesos()` compara las **dos ultimas tomas** de cada indicador (no
la primera con la ultima): interesa quien viene cayendo ahora, no como empezo
el anio. En los tiempos, subir es empeorar, y eso ya lo sabe
`Indicador.es_mejora()`.

Se ve en dos lugares: el bloque del tablero y la pantalla completa
`adm_evaluacion?action=bajando`, que ademas trae el boton para anotar al chico
y el de WhatsApp a la familia.

Bajar una vez es normal (cansancio, enfermedad, desanimo) y la pantalla lo dice
en voz alta: esto es para conversar a tiempo, no para castigar.

## Turnos de la semana (modulo adm_turno)

Quien dirige cada grupo esta semana. `TurnoSemanal` (categoria, semana,
entrenador, nota) es unico por grupo y semana, y `lunes_de()` normaliza
cualquier fecha al lunes de su semana, para que todos hablen de la misma.

La pantalla muestra una semana completa con todos los grupos, se navega con las
flechas y **se guarda sola** al elegir el profe. El boton "repetir la semana
pasada" copia lo que ya estaba (sin pisar lo que ya se decidio para esta).

Solo se ofrecen los entrenadores que ya estan asignados al grupo. El
administrador arma los turnos; el entrenador entra a ver que le toca y lo ve
tambien en su tablero ("Esta semana te toca...").

## El tablero mira la plata completa

Ademas de lo cobrado del mes, el tablero muestra la **deuda total** (todo lo
pendiente, no solo lo de este mes), cuanto esta vencido, cuanto por vencer y
**quien debe mas**, ordenado por monto. `dashboard.deuda_completa()`.

## Grupo y division: dos cosas distintas

- El **grupo** (`Categoria`) dice **cuando** entrena: MANANA, TARDE, NOCHE. En
  un mismo horario pueden estar mezclados chicos de varias edades.
- La **division** (`Division`) dice **contra quien** juega: SUB-10, SUB-12...
  Sale sola de la edad, no se asigna a mano, y se administra abajo en la
  pantalla de Categorias.

`Jugador.division()` busca la division activa cuyo rango cubre su edad, y
`Division.rango_de_nacimiento()` traduce el rango de edades a fechas de
nacimiento para poder filtrar en la base (sin recorrer jugador por jugador).
Los rangos no se pueden cruzar: el formulario lo valida.

La division sale como chip en la ficha, en la lista de jugadores (con su
filtro) y en la pantalla de asistencia, que es donde importa cuando el grupo
esta mezclado.

## Una prueba puede durar varios dias

`Evaluacion.fecha_fin` es opcional. Si se llena, la prueba se toma entre esas
dos fechas: al que falto el primer dia se le mide despues **y queda con SU
fecha**, no con la del dia en que arranco.

Eso lo guarda `Medicion.fecha`, que se pone sola al anotar el valor
(`Evaluacion.dia_para_medir()`): si hoy cae dentro del rango, queda hoy; si la
prueba ya paso, queda el dia en que arranco. `Medicion.dia()` es el dia real y
es el que manda en el progreso, en el filtro por fechas y en la comparacion con
la toma anterior.

En el historial de cada indicador, la toma enlaza a la planilla de ese dia,
para ver que paso ahi.

## Peso y estatura: van aparte

`ControlFisico` (jugador, fecha, peso, estatura, observacion) NO es un
indicador de prueba y se guarda aparte a proposito: el peso y la estatura no
son una marca que se mejora, son un ninio creciendo. No entran al radar ni se
comparan con el grupo.

Se registran desde el bloque **Peso y estatura** de la ficha, uno por dia
(la base no deja dos del mismo dia). Muestra el ultimo peso, la ultima
estatura, el IMC y cuanto crecio entre el primer control y el ultimo.

Por eso ESTATURA y PESO CORPORAL ya no se siembran como indicadores en
`cargar_base`.

## Que hay que cuidarle

`Jugador.cuidados` guarda lo que el profe tiene que saber para no exigirle de
mas: asma, alergias, una fascitis, una lesion vieja. Sale como aviso amarillo
arriba de su ficha y como etiqueta en la lista de asistencia y en la planilla,
que es donde el profe lo va a ver justo antes de ponerlo a entrenar.

## Selector de indicadores

Con muchos indicadores una lista plana de casillas es inmanejable. El modal de
la evaluacion los agrupa por area (`adm_evaluacion/selector.html`), con
buscador, contador de marcados y un "marcar toda" por area. Las casillas son
las del formulario, asi que el POST no cambia.

La planilla tambien tiene buscador de jugadores, igual que la asistencia.

## Ajustar el valor de un mes

Lo normal es que todos paguen el valor de su grupo, pero un mes puede salir
distinto (subio el precio, un acuerdo suelto). En el cobro se puede cambiar
**Valor de este mes** (`valor_completo`): eso afecta SOLO a esa mensualidad, y
la rebaja por dias que no viene se calcula sobre el valor nuevo. Si se deja
vacio, no se toca lo que ya costaba.

## Abrir el siguiente mes de un clic

En la ficha, el boton **Siguiente mes** abre la mensualidad que sigue de ese
jugador sin llenar ningun formulario: arranca el dia despues de que termino la
anterior y queda pendiente, igual que si se hubiera abierto sola. Es el
"continuar" para el caso de uno solo; el resto lo hace el cobro automatico.

## Prueba de humo

`jogabonito/tests/test_humo.py` abre TODAS las pantallas y modales del sistema
(con los dos roles, y tambien con la base vacia) y verifica que respondan 200.
No revisa logica: revisa que ningun cambio deje una plantilla rota o un modal
apuntando a algo que ya no existe. Si se agrega una pantalla, va ahi.

## Que ve el entrenador

Su menu tiene **dos modulos**: `adm_asistencia` y `adm_evaluacion`. Nada mas:
no ve plata, ni fichas, ni turnos, ni el tablero.

Por eso las **notas del profe** y el **peso y estatura** viven dentro de
`adm_evaluacion` (acciones `nota`, `borrarnota`, `control`, `editcontrol`,
`borrarcontrol`): son cosas que el profe anota de sus jugadores, y tiene que
poder hacerlas desde el modulo que si tiene. El alcance por categoria no
cambia: solo toca a los jugadores de sus grupos.

La pantalla de asistencia **abre sola en el grupo que entrena hoy** (o en el
primero que tenga), asi el profe entra y ya tiene la lista para marcar. Arriba
le sale *"Hoy te toca..."* si esta asignado ese dia.

## Quien esta a cargo de cada grupo (modulo adm_turno)

Lo mas simple que se puede: **un grupo, un profe encargado**
(`Categoria.encargado`). Se elige de una lista con los entrenadores que ya
estan en el grupo y se guarda solo; cuando haga falta, se cambia.

No hay planes por dia ni reemplazos registrados: si un dia lo cubre otro, eso
se conversa. **El encargado no manda sobre la asistencia**: cualquiera del
cuerpo tecnico puede tomar lista cualquier dia.

El modulo es del administrador. El profe ve de que grupos esta a cargo en su
propia pantalla de asistencia ("Hoy te toca...").

## Prueba individual y prueba de todo el grupo

`Evaluacion.jugador` es opcional. Vacio = se le toma a todo el grupo; con un
jugador = **prueba individual**, para el que recien llega o el que hay que
medir aparte. Las dos alimentan el mismo progreso: las mediciones son del
jugador, no de la prueba.

## Con que llego y como va

En la pantalla de progreso sale el bloque **Como llego y como va**: por cada
indicador, la marca de su prueba **inicial** contra la de hoy, con cuanto
cambio y en cuantos dias. La base es el tipo de evaluacion marcado como
`es_inicial`; si no hay ninguno, se usa la primera vez que se le midio cada
cosa. Es lo que se le muestra al representante.

## Datos de arranque de la academia

```
python manage.py cargar_academia            # Kevyn como entrenador y los tres alumnos
python manage.py cargar_academia --limpiar  # ademas borra lo de prueba
```

Deja la base como esta hoy la academia: **Kevyn Supe** con ficha de entrenador
(es el duenio y ademas dirige), el grupo **NOCHE** a su cargo y sus tres
alumnos — Edison Moyolema, Christian Moyolema y Luis Sailema — con su historia
completa: tres pruebas (la de ingreso, el control del mes y el seguimiento de
la semana), peso y estatura, notas del profe y las mensualidades abiertas desde
su fecha de ingreso, con el primer mes pagado.

Hay huecos a proposito en las mediciones (a Luis le falto una toma): asi se ve
como queda el sistema cuando alguien no da una prueba.

`--limpiar` borra los jugadores que no son esos tres y las pruebas que quedan
sin ninguna medicion. Es para dejar la base lista para mostrarla.

## Subirlo al servidor

Todo lo del despliegue esta en la carpeta [despliegue/](despliegue/README.md):
el script, el servicio de systemd, el sitio de Nginx y la tarea diaria.

```bash
sudo bash /opt/jogabonito/despliegue/desplegar.sh --primera-vez   # la primera vez
sudo bash /opt/jogabonito/despliegue/desplegar.sh                 # cada actualizada
```

El `.env` **nunca** se sube al repositorio: en el servidor se crea a mano
copiando `.env.example`. Y la clave del administrador de produccion no puede
ser la de desarrollo.

## Buscador en listas largas

La pantalla de asistencia tiene un filtro que esconde a los que no coinciden
mientras se escribe, con un boton **Ver todos** para limpiarlo. Con 46 jugadores
en un grupo es la diferencia entre encontrar al chico en dos segundos o
desplazarse toda la lista en el telefono.

## Panel lateral contraido

`app_new.css` (heredado de jdsistemas) solo sabe contraer los bloques que ya
existian ahi. Los propios de este proyecto (el menu de modulos, el copyright y
el credito de HORUS) se ajustan al final de `joga.css`, bajo
`.app.op-mini`. Si se agrega otro bloque al sidebar, hay que decidir ahi que
pasa con el cuando el panel esta contraido.
